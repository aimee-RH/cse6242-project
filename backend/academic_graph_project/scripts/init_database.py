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
        print(f"等待中... {i + 1}/30 秒")
        time.sleep(1)
    print("等待完成")


def init_database():
    print("开始初始化数据库...")
    uri = "bolt://localhost:7688"
    user = "neo4j"
    password = "academic123"

    print(f"连接信息: {uri}, 用户: {user}")

    driver = None
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

            # 1. 创建唯一性约束 (带 IF NOT EXISTS 防止报错)
            session.run("CREATE CONSTRAINT UniqueWorkIdConstraint IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE")
            print("✓ UniqueWorkIdConstraint 检查/创建完成")

            session.run(
                "CREATE CONSTRAINT UniqueAuthorIdConstraint IF NOT EXISTS FOR (a:Author) REQUIRE a.id IS UNIQUE")
            print("✓ UniqueAuthorIdConstraint 检查/创建完成")

            session.run(
                "CREATE CONSTRAINT UniqueSubfieldIdConstraint IF NOT EXISTS FOR (s:Subfield) REQUIRE s.id IS UNIQUE")
            print("✓ UniqueSubfieldIdConstraint 检查/创建完成")

            session.run("CREATE CONSTRAINT UniqueFieldIdConstraint IF NOT EXISTS FOR (f:Field) REQUIRE f.id IS UNIQUE")
            print("✓ UniqueFieldIdConstraint 检查/创建完成")

            session.run(
                "CREATE CONSTRAINT UniqueSourceIdConstraint IF NOT EXISTS FOR (so:Source) REQUIRE so.id IS UNIQUE")
            print("✓ UniqueSourceIdConstraint 检查/创建完成")

            # 2. 创建索引
            session.run("CREATE INDEX PaperTitleIndex IF NOT EXISTS FOR (p:Paper) ON (p.title)")
            print("✓ PaperTitleIndex 检查/创建完成")

            session.run("CREATE INDEX PaperPublicationYearIndex IF NOT EXISTS FOR (p:Paper) ON (p.publication_year)")
            print("✓ PaperPublicationYearIndex 检查/创建完成")

            session.run("CREATE INDEX PaperFWCIIndex IF NOT EXISTS FOR (p:Paper) ON (p.fwci)")
            print("✓ PaperFWCIIndex 检查/创建完成")

            print("索引和约束创建完成")
            print("开始导入论文数据 (分批处理)...")

            # 3. 创建论文节点 (每 500 行提交一次事务)
            session.run("""
                LOAD CSV WITH HEADERS FROM 'file:///concatenated_openalex_complete.csv' AS row 
                WITH row WHERE row.id IS NOT NULL AND row.id <> ''
                CALL {
                    WITH row
                    MERGE (p:Paper {id: row.id})
                    SET 
                      p.title = row.title,
                      p.publication_year = toInteger(row.publication_year),
                      p.fwci = toFloat(row.fwci),
                      p.cited_by_count = toInteger(row.cited_by_count),
                      p.citation_normalized_percentile = toFloat(row.`citation_normalized_percentile.value`),
                      p.is_in_top_1_percent = row.`citation_normalized_percentile.is_in_top_1_percent` = 'TRUE',
                      p.is_in_top_10_percent = row.`citation_normalized_percentile.is_in_top_10_percent` = 'TRUE'
                } IN TRANSACTIONS OF 500 ROWS
            """)
            print("✓ 论文数据导入完成")

            print("开始导入研究主题层次...")

            # 4. 创建研究主题层次 (分批处理)
            # 创建子领域节点
            session.run("""
                LOAD CSV WITH HEADERS FROM 'file:///concatenated_openalex_complete.csv' AS row
                WITH row WHERE row.`primary_topic.subfield.id` IS NOT NULL AND row.`primary_topic.subfield.id` <> ''
                CALL {
                    WITH row
                    MERGE (s:Subfield {id: row.`primary_topic.subfield.id`})
                    SET s.display_name = row.`primary_topic.subfield.display_name`

                    WITH s, row
                    MATCH (p:Paper {id: row.id})
                    MERGE (p)-[:IN_SUBFIELD]->(s)
                } IN TRANSACTIONS OF 500 ROWS
            """)
            print("✓ 子领域节点创建完成")

            # 创建领域节点
            session.run("""
                LOAD CSV WITH HEADERS FROM 'file:///concatenated_openalex_complete.csv' AS row
                WITH row WHERE row.`primary_topic.field.id` IS NOT NULL AND row.`primary_topic.field.id` <> ''
                CALL {
                    WITH row
                    MERGE (f:Field {id: row.`primary_topic.field.id`})
                    SET f.display_name = row.`primary_topic.field.display_name`

                    // 建立子领域与领域的层次关系
                    WITH f, row
                    MATCH (s:Subfield {id: row.`primary_topic.subfield.id`})
                    MERGE (s)-[:PART_OF_FIELD]->(f)
                } IN TRANSACTIONS OF 500 ROWS
            """)
            print("✓ 领域节点创建完成")

            print("开始导入来源节点...")

            # 5. 创建来源节点 (分批处理)
            session.run("""
                LOAD CSV WITH HEADERS FROM 'file:///concatenated_openalex_complete.csv' AS row
                WITH row WHERE row.`primary_location.source.id` IS NOT NULL AND row.`primary_location.source.id` <> ''
                CALL {
                    WITH row
                    MERGE (so:Source {id: row.`primary_location.source.id`})
                    SET 
                      so.display_name = row.`primary_location.source.display_name`,
                      so.type = row.`primary_location.source.type`

                    WITH so, row
                    MATCH (p:Paper {id: row.id})
                    MERGE (p)-[:PUBLISHED_IN]->(so)
                } IN TRANSACTIONS OF 500 ROWS
            """)
            print("✓ 来源节点创建完成")

            print("开始导入作者和合作关系...")

            # 6. 创建作者和合作关系 (分批处理)
            # 修正：统一使用 concatenated_openalex_complete.csv
            session.run("""
                LOAD CSV WITH HEADERS FROM 'file:///concatenated_openalex_complete.csv' AS row
                WITH row
                WHERE row.`authorships.author.id` IS NOT NULL

                CALL {
                    WITH row
                    WITH row, 
                         split(replace(replace(row.`authorships.author.id`, '[', ''), ']', ''), ',') AS authorIds,
                         split(replace(replace(row.`authorships.author.display_name`, '[', ''), ']', ''), ',') AS authorNames
                    WHERE size(authorIds) > 0 AND authorIds[0] <> ''

                    UNWIND range(0, size(authorIds)-1) AS index
                    WITH row, trim(authorIds[index]) AS authorId, trim(authorNames[index]) AS authorName, index
                    WHERE authorId <> ''

                    MERGE (a:Author {id: authorId})
                    SET a.display_name = authorName

                    WITH a, row, index
                    MATCH (p:Paper {id: row.id})
                    MERGE (a)-[:AUTHORED {authorship_order: index + 1}]->(p)
                } IN TRANSACTIONS OF 500 ROWS
            """)
            print("✓ 作者和合作关系创建完成")

            # 7. 验证数据 (简化查询，避免内存溢出)
            print("\n开始进行最终数据验证...")
            # 使用 count(*) 而不是 labels(n) 分组，减少内存消耗
            result = session.run("MATCH (n) RETURN count(n) as total_nodes")
            total_nodes = result.single()["total_nodes"]
            print(f"数据库初始化成功！当前数据库总节点数: {total_nodes}")

            result = session.run("CALL db.schema.visualization()")
            print("数据库架构验证完成！")

    except Exception as e:
        print(f"!!! 发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.close()
            print("Driver 已关闭")


if __name__ == "__main__":
    wait_for_neo4j()
    init_database()
    print("=== 脚本执行结束 ===")