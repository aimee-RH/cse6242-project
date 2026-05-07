# scripts/verify_bge_fix.py
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

INSTRUCTION = "Given a web search query, retrieve relevant passages that answer the query: "

queries = [
    "federated learning privacy",  # 之前数据库只有 19 篇，看是否能找到
    "matrix completion algorithms",  # 之前只有 5 篇
    "deep learning",  # 超泛化
    "graph neural network",  # 中等专业度
    "change point detection",  # 之前成功
    "reinforcement learning robotics",  # 之前成功
    "wireless sensor networks",  # 大数据主题
    "computer vision",  # 刚测试通过
]

for query in queries:
    query_with_inst = INSTRUCTION + query
    query_emb = model.encode(query_with_inst, normalize_embeddings=True).tolist()

    with driver.session(database=db) as sess:
        result = sess.run("""
        CALL db.index.vector.queryNodes('paper_embedding_idx', 5, $emb)
        YIELD node, score
        OPTIONAL MATCH (node)-[:IN_SUBFIELD]->(s:Subfield)
        RETURN node.title AS title, score, s.display_name AS subfield
        ORDER BY score DESC
        """, emb=query_emb)

        rows = [dict(r) for r in result]

    print(f"\n{'=' * 70}")
    print(f"Query: {query}")
    print(f"Top 1: [{rows[0]['score']:.3f}] [{rows[0]['subfield']}]")
    print(f"  {rows[0]['title'][:80]}")
    print(f"Top 5 subfield 分布:")
    for r in rows[:5]:
        sf = r['subfield'][:40] if r['subfield'] else "?"
        print(f"  [{r['score']:.3f}] [{sf}]")

driver.close()