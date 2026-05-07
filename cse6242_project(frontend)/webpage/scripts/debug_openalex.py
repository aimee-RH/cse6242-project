# scripts/debug_abstract_fetch.py
import os
import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# 从 Neo4j 取 50 个没有 abstract 的 paper id
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as sess:
    result = sess.run(
        "MATCH (p:Paper) WHERE p.abstract IS NULL RETURN p.id AS id LIMIT 50"
    )
    paper_ids = [r["id"] for r in result]

print(f"Testing with {len(paper_ids)} paper ids")
print(f"First 3: {paper_ids[:3]}")

# 去掉 URL 前缀
short_ids = [pid.replace("https://openalex.org/", "") for pid in paper_ids]
filter_str = "|".join(short_ids)

# 调 API
resp = requests.get(
    "https://api.openalex.org/works",
    params={
        "filter": f"openalex:{filter_str}",
        "per-page": 50,
        "select": "id,abstract_inverted_index,title",
        "mailto": "your_email@example.com",  # 改成你的邮箱
    },
    timeout=30,
)

print(f"\nStatus: {resp.status_code}")
print(f"URL: {resp.url[:200]}")

data = resp.json()
print(f"Meta: {data.get('meta')}")
print(f"Results count: {len(data.get('results', []))}")

# 对比传入和返回
returned_ids = {w["id"] for w in data.get("results", [])}
missing = [pid for pid in paper_ids if pid not in returned_ids]
print(f"\n❌ Missing from response: {len(missing)}")
if missing:
    print(f"  First 5 missing ids: {missing[:5]}")

# 统计返回的有多少有 abstract
has_abstract = sum(
    1 for w in data.get("results", [])
    if w.get("abstract_inverted_index")
)
no_abstract = sum(
    1 for w in data.get("results", [])
    if not w.get("abstract_inverted_index")
)
print(f"\n📊 返回的 {len(data.get('results', []))} 个 paper 中:")
print(f"  有 abstract: {has_abstract}")
print(f"  没 abstract: {no_abstract}")

driver.close()