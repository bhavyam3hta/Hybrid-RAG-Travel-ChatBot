import json
import re
from typing import List
from google import genai
from pinecone import Pinecone, ServerlessSpec
from neo4j import GraphDatabase
import config

EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL = "gemini-3.5-flash-lite"
TOP_K = 5
INDEX_NAME = config.PINECONE_INDEX_NAME

try:
    gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
    print("✅ Google Gemini client initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Gemini client: {e}")
    exit(1)

try:
    pc = Pinecone(api_key=config.PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)
    print("✅ Pinecone client initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Pinecone client: {e}")
    exit(1)

try:
    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    with driver.session() as session:
        session.run("RETURN 1")
    print("✅ Neo4j connection established successfully")
except Exception as e:
    print(f"❌ Failed to connect to Neo4j: {e}")
    exit(1)


def embed_text(text: str) -> List[float]:
    """Generates a 768-dim Gemini embedding for the user query."""
    try:
        res = gemini_client.models.embed_content(
            model=EMBED_MODEL,
            contents=text,
            config={"output_dimensionality": config.PINECONE_VECTOR_DIM}
        )
        return res.embeddings[0].values
    except Exception as e:
        print(f"❌ Error creating embedding: {e}")
        raise


def pinecone_query(query_text: str, top_k=TOP_K):
    """Embeds the query and retrieves the top-k most similar vectors from Pinecone."""
    try:
        vec = embed_text(query_text)
        res = index.query(vector=vec, top_k=top_k, include_metadata=True, include_values=False)
        print(f"🔍 Found {len(res['matches'])} relevant matches")
        return res["matches"]
    except Exception as e:
        print(f"❌ Error querying Pinecone: {e}")
        raise


def fetch_graph_context(node_ids: List[str]):
    """Fetches neighboring nodes and relationship types from Neo4j for a list of node IDs."""
    facts = []
    try:
        with driver.session() as session:
            for nid in node_ids:
                q = (
                    "MATCH (n:Entity {id:$nid})-[r]-(m:Entity) "
                    "RETURN type(r) AS rel, labels(m) AS labels, m.id AS id, "
                    "m.name AS name, m.type AS type, m.description AS description "
                    "LIMIT 10"
                )
                recs = session.run(q, nid=nid)
                for r in recs:
                    facts.append({
                        "source": nid,
                        "rel": r["rel"],
                        "target_id": r["id"],
                        "target_name": r["name"] or r["id"],
                        "target_desc": (r["description"] or "")[:400],
                        "labels": r["labels"]
                    })
        print(f"🗺️  Retrieved {len(facts)} graph relationships")
        return facts
    except Exception as e:
        print(f"❌ Error fetching graph context: {e}")
        return []


def build_prompt(user_query, pinecone_matches, graph_facts):
    """Builds a prompt string combining Pinecone vector results and Neo4j graph facts."""
    def _is_placeholder(name: str) -> bool:
        if not name:
            return True
        low = name.lower()
        if re.search(r"\battraction\b", low) and re.search(r"\d+", low):
            return True
        if re.match(r"attraction[_ ]?\d+", low):
            return True
        return False

    vec_context = []
    for m in pinecone_matches:
        meta = m.get("metadata", {}) or {}
        score = m.get("score", None)
        raw_name = (meta.get("name") or "").strip()
        if _is_placeholder(raw_name):
            city = meta.get("city") or meta.get("region") or "Unknown location"
            desc = (meta.get("description") or meta.get("semantic_text") or "").strip()
            desc_snip = (desc[:120] + "...") if desc and len(desc) > 120 else desc
            display_name = f"{city} - {desc_snip}" if desc_snip else city
        else:
            display_name = raw_name

        snippet = f"- id: {m['id']}, name: {display_name}, type: {meta.get('type','')}, score: {score}"
        if meta.get("city"):
            snippet += f", city: {meta.get('city')}"
        vec_context.append(snippet)

    graph_context = [
        f"- ({f['source']}) -[{f['rel']}]-> ({f['target_id']}) {f['target_name']}: {f['target_desc']}"
        for f in graph_facts
    ]

    prompt = (
        f"You are a knowledgeable travel guide for Vietnam. Answer the user directly and concisely using the context below. "
        f"Do not use em-dashes or en-dashes; use standard hyphens or commas instead. Avoid AI filler greetings or disclaimers.\n\n"
        f"User query: {user_query}\n\n"
        "Top semantic matches (from Pinecone Vector DB):\n" + "\n".join(vec_context[:10]) + "\n\n"
        "Knowledge Graph facts (from Neo4j):\n" + "\n".join(graph_context[:20]) + "\n\n"
        "Based on the above, answer the user's travel question. Suggest 2-3 concrete tips or itinerary steps and cite node IDs."
    )
    return prompt


def clean_ai_identifiers(text: str) -> str:
    """Removes unicode dashes, smart quotes, and robotic AI filler text."""
    if not text:
        return ""
    # Unicode dashes (em-dash, en-dash, horizontal bar) to standard hyphen
    for ch in ["\u2014", "\u2013", "\u2012", "\u2015"]:
        text = text.replace(ch, " - ")
    # Smart quotes to standard ASCII quotes
    for ch in ["\u2018", "\u2019"]:
        text = text.replace(ch, "'")
    for ch in ["\u201c", "\u201d"]:
        text = text.replace(ch, '"')
    # Ellipsis
    text = text.replace("\u2026", "...")
    # Normalize multiple hyphens or spaces
    import re
    text = re.sub(r' +(-)', r' \1', text)
    # Strip robotic AI conversational greetings
    ai_greetings = [
        r'^(?:Hey there!|Hello!|Hi there!|Greetings!|Sure thing!|Certainly!|Sure!|As an AI language model,|As an AI travel assistant,|As an AI,)\s*',
        r'^(?:Here is a recommended itinerary|Here are some recommendations|Here are the top recommendations)[^\n]*:\s*'
    ]
    for pat in ai_greetings:
        text = re.sub(pat, '', text, flags=re.IGNORECASE)
    # Strip robotic AI sign-offs
    ai_signoffs = [
        r'\n*(?:Hope this helps!|Let me know if you need more information!|Feel free to ask if you have more questions!|Safe travels and enjoy your trip!|Safe travels!)\s*$'
    ]
    for pat in ai_signoffs:
        text = re.sub(pat, '', text, flags=re.IGNORECASE)
    return text.strip()


def call_chat(prompt_text):
    """Sends prompt to Gemini chat model and returns the response text."""
    resp = gemini_client.models.generate_content(
        model=CHAT_MODEL,
        contents=prompt_text
    )
    return clean_ai_identifiers(resp.text)


def interactive_chat():
    """Runs the main chat loop, taking user questions and printing AI-generated travel answers."""
    print("\n🌏 Hybrid Travel Assistant for Vietnam (Powered by Gemini + Neo4j + Pinecone)")
    print("=" * 68)
    print("Ask me about Vietnamese destinations, culture, food, and travel tips!")
    print("Type 'exit' or 'quit' to end the conversation.\n")

    while True:
        try:
            query = input("\n🗣️  Enter your travel question: ").strip()
            if not query or query.lower() in ("exit", "quit"):
                print("\n👋 Thanks for using the travel assistant! Safe travels!")
                break

            print("\n🔍 Searching for relevant information...")

            try:
                matches = pinecone_query(query, top_k=TOP_K)
                if not matches:
                    print("⚠️  No relevant information found. Try a different question.")
                    continue
            except Exception as e:
                print(f"❌ Error searching Pinecone: {e}")
                continue

            try:
                match_ids = [m["id"] for m in matches]
                graph_facts = fetch_graph_context(match_ids)
            except Exception as e:
                print(f"❌ Error fetching graph context: {e}")
                graph_facts = []

            try:
                prompt = build_prompt(query, matches, graph_facts)
                answer = call_chat(prompt)
                print("\n🤖 Assistant Answer")
                print("=" * 50)
                print(answer)
                print("=" * 50)
            except Exception as e:
                print(f"❌ Error generating response: {e}")
                print("Please try rephrasing your question.")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Thanks for using the travel assistant!")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            print("Please try again or restart the application.")


if __name__ == "__main__":
    try:
        interactive_chat()
    except Exception as e:
        print(f"\n❌ Application error: {e}")
    finally:
        if "driver" in globals():
            driver.close()
            print("\n🔐 Database connections closed.")
