# scripts/test_similarity.py
import os
import numpy as np
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as sess:
    # 随便取两篇同 subfield 和两篇不同 subfield 的论文
    result = sess.run("""
    MATCH (p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
    WHERE p.embedding IS NOT NULL
    RETURN p.title AS title, p.embedding AS emb, s.display_name AS subfield
    LIMIT 20
    """)
    papers = [dict(r) for r in result]

# 计算余弦相似度（因为归一化了，就是点积）
def cos_sim(a, b):
    return np.dot(a, b)

print("论文两两相似度：\n")
for i in range(min(3, len(papers))):
    for j in range(i+1, min(i+4, len(papers))):
        sim = cos_sim(np.array(papers[i]["emb"]), np.array(papers[j]["emb"]))
        same_field = "✅" if papers[i]["subfield"] == papers[j]["subfield"] else "  "
        print(f"  {same_field} sim={sim:.3f}")
        print(f"     [{papers[i]['subfield']}] {papers[i]['title'][:60]}...")
        print(f"     [{papers[j]['subfield']}] {papers[j]['title'][:60]}...")
        print()

driver.close()