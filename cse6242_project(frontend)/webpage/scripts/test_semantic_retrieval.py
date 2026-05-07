# scripts/test_semantic_retrieval.py
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

load_dotenv()

model = SentenceTransformer("BAAI/bge-m3", device="mps")
print("模型加载完成")

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)
db = os.getenv("NEO4J_DATABASE", "neo4j")

# 测试几个自然语言 query
# 在之前的 test_semantic_retrieval.py 里换 queries
queries = [
    "sensor networks wireless",          # 你数据里应该有
    "machine learning statistical analysis", # 泛化查询
    "deep learning",                      # 极泛化查询
    "graph neural network",               # 中等专业度
]

for query in queries:
    print(f"\n{'=' * 70}")
    print(f"Query: {query}")
    print('=' * 70)

    query_emb = model.encode(query, normalize_embeddings=True).tolist()

    with driver.session(database=db) as sess:
        result = sess.run("""
        CALL db.index.vector.queryNodes('paper_embedding_idx', 5, $emb)
        YIELD node, score
        OPTIONAL MATCH (a:Author)-[:AUTHORED]->(node)
        WITH node, score, collect(a.display_name)[..3] AS authors
        RETURN node.title AS title, 
               score,
               node.cited_by_count AS citations,
               node.publication_year AS year,
               authors
        ORDER BY score DESC
        """, emb=query_emb)

        for i, row in enumerate(result, 1):
            authors_str = ", ".join(row["authors"][:3])
            print(f"\n  #{i} [score={row['score']:.3f}] ({row['year']}, cited {row['citations']})")
            print(f"    {row['title'][:100]}")
            print(f"    Authors: {authors_str}")

driver.close()