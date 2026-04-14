from neo4j import GraphDatabase

def run_demo_queries():
    uri = "bolt://localhost:7688"
    user = "neo4j"
    password = "academic123"
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    queries = {
        "统计各类型节点数量": "MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY count DESC",
        "高引用论文TOP10": "MATCH (p:Paper) RETURN p.title, p.total_citations ORDER BY p.total_citations DESC LIMIT 10",
        "热门研究领域": "MATCH (r:ResearchArea)<-[:IN_RESEARCH_AREA]-(:Paper) RETURN r.name, count(*) as paper_count ORDER BY paper_count DESC LIMIT 10",
        "最多产作者TOP10": "MATCH (a:Author)-[:AUTHORED]->(p:Paper) RETURN a.author_id, count(p) as paper_count ORDER BY paper_count DESC LIMIT 10"
    }
    
    with driver.session() as session:
        for name, query in queries.items():
            print(f"\n=== {name} ===")
            result = session.run(query)
            for record in result:
                print(record.data())
    
    driver.close()

if __name__ == "__main__":
    run_demo_queries()