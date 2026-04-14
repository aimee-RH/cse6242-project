from neo4j import GraphDatabase
import time
import os
import sys

print("=== 脚本开始执行 ===")
print(f"Python 版本: {sys.version}")
print(f"当前目录: {os.getcwd()}")

def wait_for_neo4j():
    """等待 Neo4j 完全启动"""
    print("等待 Neo4j 启动...")
    for i in range(30):
        print(f"等待中... {i+1}/30 秒")
        time.sleep(1)
    print("等待完成")

def init_database():
    print("开始初始化数据库...")
    uri = "bolt://localhost:7688"
    user = "neo4j"
    password = "academic123"
    
    print(f"连接信息: {uri}, 用户: {user}")
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Driver 创建成功")
        
        # 测试连接
        print("测试数据库连接...")
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            test_value = result.single()["test"]
            print(f"连接测试成功: {test_value}")
            
        print("开始执行初始化语句...")
        
        with driver.session() as session:
            print("创建索引和约束...")
            
            # 1. 创建索引和约束
            session.run("CREATE INDEX PaperTitleIndex FOR (p:Paper) ON (p.title)")
            print("✓ PaperTitleIndex 创建完成")
            
            session.run("CREATE CONSTRAINT UniqueConceptConstraint FOR (c:Concept) REQUIRE c.name IS UNIQUE")
            print("✓ UniqueConceptConstraint 创建完成")
            
            session.run("CREATE CONSTRAINT UniqueResearchAreaConstraint FOR (r:ResearchArea) REQUIRE r.name IS UNIQUE")
            print("✓ UniqueResearchAreaConstraint 创建完成")
            
            session.run("CREATE CONSTRAINT UniqueAuthorIdConstraint FOR (a:Author) REQUIRE a.author_id IS UNIQUE")
            print("✓ UniqueAuthorIdConstraint 创建完成")
            
            session.run("CREATE CONSTRAINT UniqueWorkIdConstraint FOR (p:Paper) REQUIRE p.work_id IS UNIQUE")
            print("✓ UniqueWorkIdConstraint 创建完成")
            
            print("索引和约束创建完成")
            print("开始导入论文数据...")
            
            # 2. 导入论文数据
            session.run("""
                LOAD CSV WITH HEADERS FROM 'file:///papers_full.csv' AS row
                WITH row WHERE row.work_id IS NOT NULL AND row.work_id <> ''
                MERGE (p:Paper {work_id: row.work_id})
                SET 
                  p.title = row.title,
                  p.publication_year = toInteger(row.publication_year),
                  p.total_citations = toInteger(coalesce(row.total_citations, '0')),
                  p.field_weighted_citation_impact = toFloat(coalesce(row.field_weighted_citation_impact, '0.0'))
            """)
            print("✓ 论文数据导入完成")
            

            print("开始导入作者关系...")
            
            # 3. 导入作者关系
            session.run("""
                LOAD CSV WITH HEADERS FROM 'file:///papers_full.csv' AS row
                WITH row, 
                    CASE 
                        WHEN row.co_author_ids IS NOT NULL AND row.co_author_ids <> '' THEN 
                            split(replace(replace(row.co_author_ids, '[', ''), ']', ''), ',') 
                        ELSE [] 
                    END AS authorIds
                UNWIND authorIds AS authorId
                WITH row, trim(authorId) AS cleanAuthorId
                WHERE cleanAuthorId <> ''
                MERGE (a:Author {author_id: cleanAuthorId})
                WITH a, row
                MATCH (p:Paper {work_id: row.work_id})
                MERGE (a)-[:AUTHORED]->(p)
            """)
            
            print("作者关系导入完成")
            print("开始导入研究领域...")
            
            # 4. 导入研究领域
            session.run("""
                LOAD CSV WITH HEADERS FROM 'file:///papers_full.csv' AS row
                WITH row WHERE row.primary_research_area IS NOT NULL AND row.primary_research_area <> ''
                MERGE (r:ResearchArea {name: row.primary_research_area})
                WITH r, row
                MATCH (p:Paper {work_id: row.work_id})
                MERGE (p)-[:IN_RESEARCH_AREA]->(r)
            """)
            
            print("研究领域导入完成")
            print("开始导入概念...")
            
            # 5. 导入概念
            session.run("""
                LOAD CSV WITH HEADERS FROM 'file:///papers_full.csv' AS row
                WITH row, 
                    CASE 
                        WHEN row.top_concepts IS NOT NULL AND row.top_concepts <> '' THEN 
                            split(replace(replace(row.top_concepts, '[', ''), ']', ''), ',') 
                        ELSE [] 
                    END AS concepts
                UNWIND concepts AS concept
                WITH row, trim(concept) AS cleanConcept
                WHERE cleanConcept <> ''
                MERGE (c:Concept {name: cleanConcept})
                WITH c, row
                MATCH (p:Paper {work_id: row.work_id})
                MERGE (p)-[:HAS_CONCEPT]->(c)
            """)
            
            print("概念导入完成")
            
            # 6. 验证数据
            result = session.run("MATCH (n) RETURN labels(n)[0] as label, count(n) as count")
            print("\n数据统计:")
            for record in result:
                print(f"  {record['label']}: {record['count']} 个节点")
            
            result = session.run("CALL db.schema.visualization()")
            print("\n数据库架构已创建完成！")
            
    except Exception as e:
        print(f"!!! 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'driver' in locals():
            driver.close()
            print("Driver 已关闭")

if __name__ == "__main__":
    wait_for_neo4j()
    init_database()
    print("=== 脚本执行结束 ===")