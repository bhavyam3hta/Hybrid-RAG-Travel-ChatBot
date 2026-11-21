from pathlib import Path
import json
import time
from tqdm import tqdm
from google import genai
from pinecone import Pinecone, ServerlessSpec
import config

DATA_FILE = Path(__file__).resolve().parent / "vietnam_travel_dataset.json"
BATCH_SIZE = 16

INDEX_NAME = config.PINECONE_INDEX_NAME
VECTOR_DIM = config.PINECONE_VECTOR_DIM  # 768

client = genai.Client(api_key=config.GEMINI_API_KEY)
pc = Pinecone(api_key=config.PINECONE_API_KEY)

existing_indexes = pc.list_indexes().names()
if INDEX_NAME not in existing_indexes:
    print(f"Creating index: {INDEX_NAME} (dim={VECTOR_DIM})")
    pc.create_index(
        name=INDEX_NAME,
        dimension=VECTOR_DIM,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
    time.sleep(2)
else:
    desc = pc.describe_index(INDEX_NAME)
    if desc.dimension != VECTOR_DIM:
        raise RuntimeError("Existing index dimensions differ. Choose a new PINECONE_INDEX_NAME; existing data will not be deleted.")

index = pc.Index(INDEX_NAME)


def get_embeddings(texts, model="gemini-embedding-001"):
    """Generates Gemini embeddings for a batch of texts with retry on rate limit."""
    for attempt in range(5):
        try:
            result = client.models.embed_content(
                model=model,
                contents=texts,
                config={"output_dimensionality": VECTOR_DIM}
            )
            return [e.values for e in result.embeddings]
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                wait_time = 20 * (attempt + 1)
                print(f"\n⏳ Rate limit reached. Backing off for {wait_time}s (attempt {attempt + 1}/5)...")
                time.sleep(wait_time)
            else:
                raise

    raise RuntimeError("Embedding request failed after five rate-limit retries")

def chunked(iterable, n):
    """Splits an iterable into chunks of size n."""
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]


def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        nodes = json.load(f)

    items = []
    for node in nodes:
        semantic_text = node.get("semantic_text") or (node.get("description") or "")[:1000]
        if not semantic_text.strip():
            continue
        meta = {
            "id": node.get("id"),
            "type": node.get("type"),
            "name": node.get("name"),
            "city": node.get("city", node.get("region", "")),
            "tags": node.get("tags", [])
        }
        items.append((node["id"], semantic_text, meta))

    print(f"Upserting {len(items)} items to Pinecone using Gemini embeddings ({VECTOR_DIM} dim)...")

    for batch in tqdm(list(chunked(items, BATCH_SIZE)), desc="Uploading batches"):
        ids = [item[0] for item in batch]
        texts = [item[1] for item in batch]
        metas = [item[2] for item in batch]

        embeddings = get_embeddings(texts)
        vectors = [
            {"id": _id, "values": emb, "metadata": meta}
            for _id, emb, meta in zip(ids, embeddings, metas)
        ]
        index.upsert(vectors=vectors)
        time.sleep(1.0)  # Gentle pacing to respect free-tier TPM limits

    print("\n✅ All items uploaded successfully to Pinecone!")


if __name__ == "__main__":
    main()
