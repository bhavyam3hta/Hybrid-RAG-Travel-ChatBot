from pathlib import Path
import json
from neo4j import GraphDatabase
from tqdm import tqdm
import config

DATA_FILE = Path(__file__).resolve().parent / "vietnam_travel_dataset.json"

try:
    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    with driver.session() as session:
        session.run("RETURN 1")
    print("✅ Neo4j connection established")
except Exception as e:
    print(f"❌ Failed to connect to Neo4j: {e}")
    exit(1)


def create_constraints(tx):
    """Creates a uniqueness constraint on the 'id' property for all Entity nodes."""
    tx.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE")


def upsert_node(tx, node):
    """Merges a node into Neo4j using its type as an additional label alongside :Entity."""
    labels = [node.get("type", "Unknown"), "Entity"]
    label_cypher = ":" + ":".join(labels)
    props = {k: v for k, v in node.items() if k not in ("connections",)}
    tx.run(
        f"MERGE (n{label_cypher} {{id: $id}}) SET n += $props",
        id=node["id"], props=props
    )


def create_relationship(tx, source_id, rel):
    """Creates a directed relationship between two Entity nodes if both exist."""
    rel_type = rel.get("relation", "RELATED_TO")
    target_id = rel.get("target")
    if not target_id:
        return
    cypher = (
        "MATCH (a:Entity {id: $source_id}), (b:Entity {id: $target_id}) "
        f"MERGE (a)-[r:{rel_type}]->(b) "
        "RETURN r"
    )
    tx.run(cypher, source_id=source_id, target_id=target_id)


def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        nodes = json.load(f)

    with driver.session() as session:
        session.execute_write(create_constraints)

        for node in tqdm(nodes, desc="Creating nodes"):
            session.execute_write(upsert_node, node)

        for node in tqdm(nodes, desc="Creating relationships"):
            for rel in node.get("connections", []):
                session.execute_write(create_relationship, node["id"], rel)

    print("Done loading into Neo4j.")


if __name__ == "__main__":
    main()
