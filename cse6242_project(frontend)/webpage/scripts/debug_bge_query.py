# scripts/debug_bge_query.py
import os
import numpy as np
from dotenv import load_dotenv
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

load_dotenv()
model = SentenceTransformer("BAAI/bge-m3", device="mps")

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)
db = os.getenv("NEO4J_DATABASE", "neo4j")

query_raw = "neural network for computer vision"

# 试 4 种 query 构造方式
queries = {
    "1. Raw (当前方式)": query_raw,

    "2. BGE English instruction":
        f"Represent this sentence for searching relevant passages: {query_raw}",

    "3. BGE-M3 retrieval instruction":
        f"Given a web search query, retrieve relevant passages that answer the query: {query_raw}",

    "4. Domain-rich rewrite":
        f"Academic papers about deep learning neural network architectures applied to computer vision, image recognition, object detection tasks. {query_raw}",
}

for label, query_text in queries.items():
    query_emb = np.array(model.encode(query_text, normalize_embeddings=True))

    with driver.session(database=db) as sess:
        result = sess.run("""
        CALL db.index.vector.queryNodes('paper_embedding_idx', 10, $emb)
        YIELD node, score
        OPTIONAL MATCH (node)-[:IN_SUBFIELD]->(s:Subfield)
        RETURN node.title AS title, score, s.display_name AS subfield
        ORDER BY score DESC
        """, emb=query_emb.tolist())

        rows = [dict(r) for r in result]

    cv_count = sum(1 for r in rows if r["subfield"] and "Vision" in r["subfield"])
    ai_count = sum(1 for r in rows if r["subfield"] and r["subfield"] == "Artificial Intelligence")

    print(f"\n{'=' * 70}")
    print(f"{label}")
    print(f"{'=' * 70}")
    print(f"Top 10 最高分: {rows[0]['score']:.3f}")
    print(f"Top 10 最低分: {rows[-1]['score']:.3f}")
    print(f"CV / AI 命中: {cv_count} / {ai_count}")
    print(f"\nTop 5:")
    for r in rows[:5]:
        sf = r['subfield'][:40] if r['subfield'] else "?"
        print(f"  [{r['score']:.3f}] [{sf:40}] {r['title'][:60]}")

driver.close()