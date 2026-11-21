import json
import re
from pathlib import Path
from typing import List
from flask import Flask, render_template, request, jsonify, send_file
from google import genai
from pinecone import Pinecone, ServerlessSpec
from neo4j import GraphDatabase
import config

app = Flask(__name__)

EMBED_MODEL = config.GEMINI_EMBED_MODEL
CHAT_MODEL = config.GEMINI_CHAT_MODEL
TOP_K = 5
INDEX_NAME = config.PINECONE_INDEX_NAME
DEMO_MODE = config.APP_MODE == "demo"
if config.APP_MODE not in ("demo", "cloud"):
    raise RuntimeError("APP_MODE must be demo or cloud")
gemini_client = pinecone_index = neo4j_driver = None
if not DEMO_MODE:
    required = ("GEMINI_API_KEY", "PINECONE_API_KEY", "NEO4J_URI", "NEO4J_PASSWORD")
    missing = [name for name in required if not getattr(config, name, "")]
    if missing:
        raise RuntimeError("Fill in config.py before using cloud mode: " + ", ".join(missing))
    gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
    pinecone_index = Pinecone(api_key=config.PINECONE_API_KEY).Index(INDEX_NAME)
    neo4j_driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    neo4j_driver.verify_connectivity()
else:
    from local_demo import answer_query


def embed_text(text: str) -> List[float]:
    """Generates a 768-dim Gemini embedding for the user search query."""
    if not gemini_client:
        raise RuntimeError("Gemini client is not initialized.")
    res = gemini_client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config={"output_dimensionality": config.PINECONE_VECTOR_DIM}
    )
    return res.embeddings[0].values


def pinecone_query(query_text: str, top_k=TOP_K):
    """Retrieves top-k similar vectors from Pinecone."""
    if not pinecone_index:
        return []
    vec = embed_text(query_text)
    res = pinecone_index.query(vector=vec, top_k=top_k, include_metadata=True, include_values=False)
    matches = []
    for m in res.get("matches", []):
        meta = m.get("metadata", {}) or {}
        matches.append({
            "id": m.get("id"),
            "score": round(float(m.get("score", 0.0)) * 100, 1),
            "name": meta.get("name") or m.get("id"),
            "type": meta.get("type", "Attraction"),
            "city": meta.get("city") or meta.get("region", "Vietnam"),
            "tags": meta.get("tags", [])
        })
    return matches


def fetch_graph_context(node_ids: List[str]):
    """Retrieves neighboring nodes and relationship facts from Neo4j."""
    facts = []
    if not neo4j_driver:
        return facts
    try:
        with neo4j_driver.session() as session:
            for nid in node_ids:
                q = (
                    "MATCH (n:Entity {id:$nid})-[r]-(m:Entity) "
                    "RETURN type(r) AS rel, labels(m) AS labels, m.id AS id, "
                    "m.name AS name, m.type AS type, m.description AS description "
                    "LIMIT 6"
                )
                recs = session.run(q, nid=nid)
                for r in recs:
                    facts.append({
                        "source": nid,
                        "rel": r["rel"],
                        "target_id": r["id"],
                        "target_name": r["name"] or r["id"],
                        "target_type": r["type"] or "Location",
                        "target_desc": (r["description"] or "")[:250]
                    })
    except Exception as e:
        print(f"Error fetching Neo4j graph context: {e}")
    return facts


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


def generate_llm_answer(user_query, matches, graph_facts):
    """Generates an answer using Google Gemini Flash."""
    vec_snips = [f"- {m['name']} ({m['city']}, {m['type']}, relevance: {m['score']}%)" for m in matches]
    graph_snips = [f"- ({f['source']}) -[{f['rel']}]-> ({f['target_name']})" for f in graph_facts[:15]]

    content = (
        f"You are a knowledgeable travel guide for Vietnam. Use the retrieved context below to provide a natural, structured recommendation.\n"
        f"Style requirements: Do not use em-dashes or en-dashes; use standard hyphens or commas instead. Avoid robotic AI conversational filler (like 'Hey there!', 'As an AI', 'Sure thing!'). Begin directly with practical suggestions, highlighting key destinations and tips.\n\n"
        f"User Query: {user_query}\n\n"
        f"Top Semantic Matches (from Pinecone Vector DB):\n" + "\n".join(vec_snips) + "\n\n"
        f"Knowledge Graph Relationships (from Neo4j):\n" + "\n".join(graph_snips) + "\n\n"
        "Provide a clear travel recommendation with destinations, activities, and travel advice."
    )

    if gemini_client:
        try:
            resp = gemini_client.models.generate_content(
                model=CHAT_MODEL,
                contents=content
            )
            return clean_ai_identifiers(resp.text)
        except Exception as e:
            print(f"⚠️ Gemini generate error: {e}")

    raise RuntimeError("Gemini could not generate an answer. Check credentials, model access and quota.")


@app.route("/")
def index():
    return render_template("index.html", demo_mode=DEMO_MODE)


@app.route("/graph-viz")
def graph_viz():
    return send_file("neo4j_viz.html")


@app.route("/lib/<path:path>")
def send_lib(path):
    from flask import send_from_directory
    return send_from_directory("lib", path)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("query"), str):
        return jsonify({"error": "Send a JSON object with a text query"}), 400
    query = data["query"].strip()
    if not query:
        return jsonify({"error": "Query cannot be empty"}), 400

    try:
        if DEMO_MODE:
            return jsonify(answer_query(query, TOP_K))
        matches = pinecone_query(query, top_k=TOP_K)
        match_ids = [m["id"] for m in matches]
        graph_facts = fetch_graph_context(match_ids)
        answer = generate_llm_answer(query, matches, graph_facts)

        return jsonify({
            "query": query,
            "answer": answer,
            "matches": matches,
            "graph_facts": graph_facts[:15]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print(f"Starting Vietnam Travel Chatbot ({config.APP_MODE}) at http://127.0.0.1:{config.PORT}")
    app.run(host="127.0.0.1", port=config.PORT, debug=False)
