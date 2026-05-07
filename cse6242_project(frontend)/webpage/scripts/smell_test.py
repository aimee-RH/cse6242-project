# scripts/smell_test.py
import os
import numpy as np
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

db = os.getenv("NEO4J_DATABASE", "neo4j")

# 测试 1: 基本数据健康
with driver.session(database=db) as sess:
    result = sess.run("""
    MATCH (p:Paper) 
    WHERE p.embedding IS NOT NULL
    RETURN count(p) AS total, 
           size(p.embedding) AS dim
    LIMIT 1
    """).single()
    print(f"[Test 1] 总计: {result['total']} embedded, 维度: {result['dim']}")

# 测试 2: 向量归一化验证（normalize_embeddings=True 应保证 norm ≈ 1）
with driver.session(database=db) as sess:
    result = sess.run("""
    MATCH (p:Paper) 
    WHERE p.embedding IS NOT NULL
    RETURN p.embedding AS emb
    LIMIT 5
    """)
    print(f"\n[Test 2] 向量 norm 检查（应该都接近 1.0）:")
    for i, row in enumerate(result):
        emb = np.array(row["emb"])
        norm = np.linalg.norm(emb)
        print(f"  向量 {i+1}: norm = {norm:.4f} {'✅' if 0.98 < norm < 1.02 else '❌'}")

# 测试 3: 同 subfield vs 不同 subfield 相似度对比
with driver.session(database=db) as sess:
    result = sess.run("""
    MATCH (p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
    WHERE p.embedding IS NOT NULL AND p.embedding_quality = 'full'
    RETURN p.title AS title, p.embedding AS emb, s.display_name AS subfield
    LIMIT 50
    """)
    papers = [dict(r) for r in result]

def cos_sim(a, b):
    return float(np.dot(np.array(a), np.array(b)))

same_sims = []
diff_sims = []
for i in range(len(papers)):
    for j in range(i+1, len(papers)):
        sim = cos_sim(papers[i]["emb"], papers[j]["emb"])
        if papers[i]["subfield"] == papers[j]["subfield"]:
            same_sims.append(sim)
        else:
            diff_sims.append(sim)

print(f"\n[Test 3] Subfield 相似度对比（来自 50 篇 full-quality 论文）:")
print(f"  同 subfield 对数:   {len(same_sims)}, 平均相似度: {np.mean(same_sims):.3f}")
print(f"  不同 subfield 对数: {len(diff_sims)}, 平均相似度: {np.mean(diff_sims):.3f}")
print(f"  差距: {np.mean(same_sims) - np.mean(diff_sims):.3f}")

if np.mean(same_sims) > np.mean(diff_sims):
    print("  ✅ 同领域相似度 > 不同领域，embedding 有语义区分力")
else:
    print("  ❌ Embedding 质量异常，需要排查")

# 测试 4: 查 Yao Xie 的论文里最相似的两篇
print(f"\n[Test 4] Yao Xie 论文内部相似度:")
with driver.session(database=db) as sess:
    result = sess.run("""
    MATCH (a:Author {id: "https://openalex.org/A5047736740"})-[:AUTHORED]->(p:Paper)
    WHERE p.embedding IS NOT NULL
    RETURN p.title AS title, p.embedding AS emb
    ORDER BY p.cited_by_count DESC
    LIMIT 5
    """)
    yao_papers = [dict(r) for r in result]

for i in range(len(yao_papers)):
    for j in range(i+1, len(yao_papers)):
        sim = cos_sim(yao_papers[i]["emb"], yao_papers[j]["emb"])
        print(f"  sim={sim:.3f}")
        print(f"    A: {yao_papers[i]['title'][:70]}...")
        print(f"    B: {yao_papers[j]['title'][:70]}...")

driver.close()
print("\n✅ Smell test 完成")