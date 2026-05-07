"""
scripts/import_neo4j.py

从 CLEANED_FORMATTED_DATA.csv 导入 OpenAlex 学术数据到 Neo4j。

运行方式:
    python scripts/import_neo4j.py

前提:
    - Neo4j 运行在 bolt://localhost:7688
    - .env 文件配置好 NEO4J_* 变量
    - CSV 文件在项目根目录或通过 --csv 指定路径
"""

import os
import sys
import csv
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
from neo4j import GraphDatabase
from tqdm import tqdm

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_list_field(raw: str) -> List[str]:
    """
    解析 "[item1,item2,item3]" 格式的字段。
    处理 CSV 里作者 id 列表和作者名字列表。
    """
    if not raw or raw.strip() in ("", "[]"):
        return []
    # 去掉首尾的 [ 和 ]
    stripped = raw.strip()
    if stripped.startswith("["):
        stripped = stripped[1:]
    if stripped.endswith("]"):
        stripped = stripped[:-1]
    # 按逗号分隔并 strip 每个元素
    items = [x.strip() for x in stripped.split(",") if x.strip()]
    return items


def parse_bool(raw: str) -> bool:
    """解析 TRUE/FALSE/true/false/1/0"""
    if not raw:
        return False
    return raw.strip().upper() in ("TRUE", "1", "YES")


def parse_float_safe(raw: str) -> float:
    """解析浮点数，失败返回 None"""
    try:
        return float(raw) if raw and raw.strip() else None
    except (ValueError, TypeError):
        return None


def parse_int_safe(raw: str) -> int:
    """解析整数"""
    try:
        return int(raw) if raw and raw.strip() else None
    except (ValueError, TypeError):
        return None


class Neo4jImporter:
    def __init__(self, uri: str, user: str, password: str, database: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def close(self):
        self.driver.close()

    def clear_database(self):
        """清空数据库（慎用！）"""
        logger.warning(f"Clearing database: {self.database}")
        with self.driver.session(database=self.database) as session:
            # 分批删除避免内存爆炸
            while True:
                result = session.run(
                    "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(n) AS deleted"
                ).single()
                deleted = result["deleted"]
                if deleted == 0:
                    break
                logger.info(f"  Deleted {deleted} nodes...")
        logger.info("Database cleared.")

    def create_constraints(self):
        """创建唯一性约束（加速后续 MERGE）"""
        logger.info("Creating constraints...")
        constraints = [
            "CREATE CONSTRAINT paper_id_unique IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT author_id_unique IF NOT EXISTS FOR (a:Author) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT subfield_id_unique IF NOT EXISTS FOR (s:Subfield) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT field_id_unique IF NOT EXISTS FOR (f:Field) REQUIRE f.id IS UNIQUE",
            "CREATE CONSTRAINT source_id_unique IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE",
        ]
        with self.driver.session(database=self.database) as session:
            for c in constraints:
                session.run(c)
                logger.info(f"  {c.split('FOR')[0].strip()}")
        logger.info("Constraints created.")

    def import_batch(self, batch: List[Dict[str, Any]]):
        """批量导入一组 paper 数据"""
        cypher = """
        UNWIND $batch AS row

        // 1. MERGE Paper 节点
        MERGE (p:Paper {id: row.paper_id})
        SET p.title = row.title,
            p.publication_year = row.publication_year,
            p.fwci = row.fwci,
            p.cited_by_count = row.cited_by_count,
            p.citation_percentile = row.citation_percentile,
            p.is_top_1_percent = row.is_top_1_percent,
            p.is_top_10_percent = row.is_top_10_percent

        // 2. MERGE Subfield 和 Field，以及它们的关系
        WITH p, row
        WHERE row.subfield_id IS NOT NULL
        MERGE (sf:Subfield {id: row.subfield_id})
        SET sf.display_name = row.subfield_name
        MERGE (p)-[:IN_SUBFIELD]->(sf)

        // 3. Field（subfield 属于 field）
        WITH p, row, sf
        WHERE row.field_id IS NOT NULL
        MERGE (f:Field {id: row.field_id})
        SET f.display_name = row.field_name
        MERGE (sf)-[:IN_FIELD]->(f)

        // 4. Source / Venue
        WITH p, row
        WHERE row.source_id IS NOT NULL
        MERGE (src:Source {id: row.source_id})
        SET src.display_name = row.source_name,
            src.type = row.source_type
        MERGE (p)-[:PUBLISHED_IN]->(src)

        // 5. Authors
        WITH p, row
        UNWIND range(0, size(row.author_ids) - 1) AS i
        WITH p, row.author_ids[i] AS aid, row.author_names[i] AS aname
        WHERE aid IS NOT NULL AND aid <> ""
        MERGE (a:Author {id: aid})
        SET a.display_name = aname
        MERGE (a)-[:AUTHORED]->(p)
        """
        with self.driver.session(database=self.database) as session:
            session.run(cypher, batch=batch)

    def get_stats(self) -> Dict[str, int]:
        """查询导入后的统计信息"""
        stats = {}
        queries = {
            "papers": "MATCH (p:Paper) RETURN count(p) AS c",
            "authors": "MATCH (a:Author) RETURN count(a) AS c",
            "subfields": "MATCH (s:Subfield) RETURN count(s) AS c",
            "fields": "MATCH (f:Field) RETURN count(f) AS c",
            "sources": "MATCH (s:Source) RETURN count(s) AS c",
            "authored_rels": "MATCH ()-[r:AUTHORED]->() RETURN count(r) AS c",
            "in_subfield_rels": "MATCH ()-[r:IN_SUBFIELD]->() RETURN count(r) AS c",
            "in_field_rels": "MATCH ()-[r:IN_FIELD]->() RETURN count(r) AS c",
            "published_in_rels": "MATCH ()-[r:PUBLISHED_IN]->() RETURN count(r) AS c",
        }
        with self.driver.session(database=self.database) as session:
            for name, q in queries.items():
                result = session.run(q).single()
                stats[name] = result["c"]
        return stats


def process_csv_row(row: Dict[str, str]) -> Dict[str, Any]:
    """把 CSV 一行解析成 Neo4j 导入需要的格式"""
    author_ids = parse_list_field(row.get("authorships.author.id", ""))
    author_names = parse_list_field(row.get("authorships.author.display_name", ""))

    # 如果长度不一致，截短到较短的
    if len(author_ids) != len(author_names):
        logger.warning(
            f"Author count mismatch in paper {row.get('id', '?')}: "
            f"{len(author_ids)} ids vs {len(author_names)} names. Using shorter."
        )
        min_len = min(len(author_ids), len(author_names))
        author_ids = author_ids[:min_len]
        author_names = author_names[:min_len]

    return {
        "paper_id": row.get("id", "").strip(),
        "title": row.get("title", "").strip(),
        "publication_year": parse_int_safe(row.get("publication_year", "")),
        "fwci": parse_float_safe(row.get("fwci", "")),
        "cited_by_count": parse_int_safe(row.get("cited_by_count", "")),
        "citation_percentile": parse_float_safe(
            row.get("citation_normalized_percentile.value", "")
        ),
        "is_top_1_percent": parse_bool(
            row.get("citation_normalized_percentile.is_in_top_1_percent", "")
        ),
        "is_top_10_percent": parse_bool(
            row.get("citation_normalized_percentile.is_in_top_10_percent", "")
        ),
        "subfield_id": row.get("primary_topic.subfield.id", "").strip() or None,
        "subfield_name": row.get("primary_topic.subfield.display_name", "").strip(),
        "field_id": row.get("primary_topic.field.id", "").strip() or None,
        "field_name": row.get("primary_topic.field.display_name", "").strip(),
        "source_id": row.get("primary_location.source.id", "").strip() or None,
        "source_name": row.get("primary_location.source.display_name", "").strip(),
        "source_type": row.get("primary_location.source.type", "").strip(),
        "author_ids": author_ids,
        "author_names": author_names,
    }


def main():
    parser = argparse.ArgumentParser(description="Import OpenAlex CSV to Neo4j")
    parser.add_argument(
        "--csv",
        default="CLEANED_FORMATTED_DATA.csv",
        help="Path to CSV file (default: CLEANED_FORMATTED_DATA.csv)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for Neo4j inserts (default: 500)",
    )
    parser.add_argument(
        "--skip-clear",
        action="store_true",
        help="Skip clearing database (for incremental imports)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only import first N rows (for testing)",
    )
    args = parser.parse_args()

    load_dotenv()

    # 读取 Neo4j 配置
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "academic_graph")

    if not password:
        logger.error("NEO4J_PASSWORD not set in .env")
        sys.exit(1)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)

    logger.info(f"Importing from: {csv_path}")
    logger.info(f"Neo4j: {uri} / database: {database}")

    # 确认操作
    if not args.skip_clear:
        response = input(
            f"\n⚠️  This will CLEAR all data in database '{database}'. Type 'yes' to proceed: "
        )
        if response.strip().lower() != "yes":
            logger.info("Aborted by user.")
            sys.exit(0)

    importer = Neo4jImporter(uri, user, password, database)

    try:
        # 1. 清空（如未跳过）
        if not args.skip_clear:
            importer.clear_database()

        # 2. 创建约束
        importer.create_constraints()

        # 3. 读 CSV 并批量导入
        logger.info(f"Reading CSV and importing (batch size: {args.batch_size})...")

        # 先数一下总行数（用于 tqdm）
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            total_rows = sum(1 for _ in f) - 1  # 减去表头
        if args.limit:
            total_rows = min(total_rows, args.limit)

        batch = []
        imported = 0
        errors = 0

        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            pbar = tqdm(total=total_rows, desc="Importing")

            for idx, row in enumerate(reader):
                if args.limit and idx >= args.limit:
                    break

                try:
                    parsed = process_csv_row(row)
                    if not parsed["paper_id"]:
                        logger.warning(f"Row {idx}: missing paper_id, skipping")
                        errors += 1
                        continue
                    batch.append(parsed)
                except Exception as e:
                    logger.error(f"Row {idx}: parse error: {e}")
                    errors += 1
                    continue

                if len(batch) >= args.batch_size:
                    try:
                        importer.import_batch(batch)
                        imported += len(batch)
                    except Exception as e:
                        logger.error(f"Batch import error at row {idx}: {e}")
                        errors += len(batch)
                    pbar.update(len(batch))
                    batch = []

            # 处理最后一批
            if batch:
                try:
                    importer.import_batch(batch)
                    imported += len(batch)
                    pbar.update(len(batch))
                except Exception as e:
                    logger.error(f"Final batch import error: {e}")
                    errors += len(batch)

            pbar.close()

        logger.info(f"\nImport complete: {imported} papers imported, {errors} errors")

        # 4. 打印统计
        logger.info("\n=== Database Statistics ===")
        stats = importer.get_stats()
        for key, val in stats.items():
            logger.info(f"  {key:25s}: {val:,}")

    finally:
        importer.close()


if __name__ == "__main__":
    main()

# import csv
# import json
# from neo4j import GraphDatabase
#
# URI = "bolt://localhost:7688"
# AUTH = ("neo4j", "academic123")
#
# def parse_list_string(s):
#     if not s or s == '':
#         return []
#     s = s.strip('[]')
#     if not s:
#         return []
#     items = []
#     for item in s.split(','):
#         item = item.strip().strip('"').strip("'")
#         if item:
#             items.append(item)
#     return items
#
# def import_csv_to_neo4j(csv_file, driver):
#     papers = []
#     authors = set()
#     venues = set()
#     fields = set()
#     subfields = set()
#     paper_authors = []
#     paper_venue = []
#     paper_field = []
#     paper_subfield = []
#
#     print(f"Reading {csv_file}...")
#     with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
#         reader = csv.DictReader(f)
#         for i, row in enumerate(reader):
#             paper_id = row['id']
#             title = row['title']
#             year = row['publication_year']
#             fwci = row['fwci']
#             cited_by = row['cited_by_count']
#
#             papers.append({
#                 'id': paper_id,
#                 'title': title,
#                 'year': year,
#                 'fwci': fwci,
#                 'cited_by': cited_by
#             })
#
#             author_ids = parse_list_string(row.get('authorships.author.id', ''))
#             author_names = parse_list_string(row.get('authorships.author.display_name', ''))
#
#             for aid, aname in zip(author_ids, author_names):
#                 if aid:
#                     authors.add((aid, aname))
#                     paper_authors.append((paper_id, aid))
#
#             venue_id = row.get('primary_location.source.id', '')
#             venue_name = row.get('primary_location.source.display_name', '')
#             venue_type = row.get('primary_location.source.type', '')
#             if venue_id:
#                 venues.add((venue_id, venue_name, venue_type))
#                 paper_venue.append((paper_id, venue_id))
#
#             field_id = row.get('primary_topic.field.id', '')
#             field_name = row.get('primary_topic.field.display_name', '')
#             if field_id:
#                 fields.add((field_id, field_name))
#                 paper_field.append((paper_id, field_id))
#
#             subfield_id = row.get('primary_topic.subfield.id', '')
#             subfield_name = row.get('primary_topic.subfield.display_name', '')
#             if subfield_id:
#                 subfields.add((subfield_id, subfield_name))
#                 paper_subfield.append((paper_id, subfield_id))
#
#     print(f"Loaded: {len(papers)} papers, {len(authors)} authors, {len(venues)} venues, {len(fields)} fields, {len(subfields)} subfields")
#
#     with driver.session() as session:
#         print("Creating constraints...")
#         session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE")
#         session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Author) REQUIRE a.id IS UNIQUE")
#         session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (v:Venue) REQUIRE v.id IS UNIQUE")
#         session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:Field) REQUIRE f.id IS UNIQUE")
#         session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Subfield) REQUIRE s.id IS UNIQUE")
#
#         print("Creating Paper nodes...")
#         for p in papers:
#             session.run("""
#                 MERGE (p:Paper {id: $id})
#                 SET p.title = $title, p.year = $year, p.fwci = $fwci, p.cited_by = $cited_by
#             """, id=p['id'], title=p['title'], year=p['year'], fwci=p['fwci'], cited_by=p['cited_by'])
#
#         print("Creating Author nodes...")
#         for aid, aname in authors:
#             session.run("MERGE (a:Author {id: $id}) SET a.name = $name", id=aid, name=aname)
#
#         print("Creating Venue nodes...")
#         for vid, vname, vtype in venues:
#             session.run("MERGE (v:Venue {id: $id}) SET v.name = $name, v.type = $type", id=vid, name=vname, type=vtype)
#
#         print("Creating Field nodes...")
#         for fid, fname in fields:
#             session.run("MERGE (f:Field {id: $id}) SET f.name = $name", id=fid, name=fname)
#
#         print("Creating Subfield nodes...")
#         for sid, sname in subfields:
#             session.run("MERGE (s:Subfield {id: $id}) SET s.name = $name", id=sid, name=sname)
#
#         print("Creating Paper->Author relationships...")
#         for paper_id, author_id in paper_authors:
#             session.run("""
#                 MATCH (p:Paper {id: $paper_id}), (a:Author {id: $author_id})
#                 MERGE (p)-[:AUTHORED_BY]->(a)
#             """, paper_id=paper_id, author_id=author_id)
#
#         print("Creating Paper->Venue relationships...")
#         for paper_id, venue_id in paper_venue:
#             session.run("""
#                 MATCH (p:Paper {id: $paper_id}), (v:Venue {id: $venue_id})
#                 MERGE (p)-[:PUBLISHED_IN]->(v)
#             """, paper_id=paper_id, venue_id=venue_id)
#
#         print("Creating Paper->Field relationships...")
#         for paper_id, field_id in paper_field:
#             session.run("""
#                 MATCH (p:Paper {id: $paper_id}), (f:Field {id: $field_id})
#                 MERGE (p)-[:IN_FIELD]->(f)
#             """, paper_id=paper_id, field_id=field_id)
#
#         print("Creating Paper->Subfield relationships...")
#         for paper_id, subfield_id in paper_subfield:
#             session.run("""
#                 MATCH (p:Paper {id: $paper_id}), (s:Subfield {id: $subfield_id})
#                 MERGE (p)-[:IN_SUBFIELD]->(s)
#             """, paper_id=paper_id, subfield_id=subfield_id)
#
#         print("Creating Field->Subfield relationships...")
#         for paper_id, field_id in paper_field:
#             for paper_id2, subfield_id in paper_subfield:
#                 if paper_id == paper_id2:
#                     session.run("""
#                         MATCH (f:Field {id: $field_id}), (s:Subfield {id: $subfield_id})
#                         MERGE (f)-[:HAS_SUBFIELD]->(s)
#                     """, field_id=field_id, subfield_id=subfield_id)
#
#         print("Import complete!")
#
# if __name__ == "__main__":
#     driver = GraphDatabase.driver(URI, auth=AUTH)
#     try:
#         import_csv_to_neo4j("data/CLEANED_FORMATTED_DATA.csv", driver)
#     finally:
#         driver.close()