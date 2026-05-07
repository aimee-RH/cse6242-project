# scripts/debug_cv_quality.py
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

query = "neural network for computer vision"
query_emb = np.array(model.encode(query, normalize_embeddings=True))

# 取 CV subfield 下所有论文，按 quality 分组
with driver.session(database=db) as sess:
    result = sess.run("""
    MATCH (p:Paper)-[:IN_SUBFIELD]->(s:Subfield {display_name: "Computer Vision and Pattern Recognition"})
    WHERE p.embedding IS NOT NULL
    RETURN p.title AS title, 
           p.embedding AS emb,
           p.embedding_quality AS quality,
           p.cited_by_count AS citations
    ORDER BY p.cited_by_count DESC
    """)
    cv_papers = [dict(r) for r in result]

print(f"CV subfield 总数: {len(cv_papers)}")

# 按 quality 分组
full_papers = [p for p in cv_papers if p["quality"] == "full"]
title_papers = [p for p in cv_papers if p["quality"] == "title_only"]
print(f"  full quality: {len(full_papers)}")
print(f"  title_only quality: {len(title_papers)}")

# 分别算和 query 的相似度
def cos_sim(a, b):
    return float(np.dot(np.array(a), np.array(b)))

full_sims = [(cos_sim(p["emb"], query_emb), p["title"][:80], p["citations"]) for p in full_papers]
title_sims = [(cos_sim(p["emb"], query_emb), p["title"][:80], p["citations"]) for p in title_papers]

full_sims.sort(reverse=True)
title_sims.sort(reverse=True)

print(f"\n【Full quality CV 论文】")
print(f"  最高相似度: {full_sims[0][0]:.3f}")
print(f"  平均相似度: {np.mean([s[0] for s in full_sims]):.3f}")
print(f"  Top 5:")
for sim, title, cite in full_sims[:5]:
    print(f"    [sim={sim:.3f}, cite={cite}] {title}")

print(f"\n【Title-only quality CV 论文】")
print(f"  最高相似度: {title_sims[0][0]:.3f}")
print(f"  平均相似度: {np.mean([s[0] for s in title_sims]):.3f}")
print(f"  Top 5:")
for sim, title, cite in title_sims[:5]:
    print(f"    [sim={sim:.3f}, cite={cite}] {title}")

# 对比：query 和一批乱七八糟的论文相似度
with driver.session(database=db) as sess:
    result = sess.run("""
    MATCH (p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
    WHERE s.display_name = "Astronomy and Astrophysics"
      AND p.embedding IS NOT NULL
    RETURN p.title AS title, p.embedding AS emb
    LIMIT 100
    """)
    astro_papers = [dict(r) for r in result]

astro_sims = [cos_sim(p["emb"], query_emb) for p in astro_papers]
print(f"\n【Astronomy 论文（作为对照）】")
print(f"  最高相似度: {max(astro_sims):.3f}")
print(f"  平均相似度: {np.mean(astro_sims):.3f}")

driver.close()