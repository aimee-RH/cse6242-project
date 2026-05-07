"""
scripts/backfill_abstract.py

从 OpenAlex API 批量补全 Paper 的 abstract 字段。

运行方式:
    python scripts/backfill_abstract.py                # 全量补
    python scripts/backfill_abstract.py --limit 100    # 测试 100 条
    python scripts/backfill_abstract.py --resume       # 断点续传

特性:
    - 断点续传（已处理 id 存在 .abstract_progress.json）
    - 礼貌限速（10 req/sec）
    - 批量查询（OpenAlex 支持 filter:openalex:id1|id2|... 一次 50 个）
    - 倒排索引还原为纯文本
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase
from tqdm import tqdm
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ========== 配置 ==========
OPENALEX_API = "https://api.openalex.org/works"
OPENALEX_MAILTO = "gaoruihuan0704@gmail.com"  # ⚠️ 改成你的邮箱
BATCH_SIZE = 50  # OpenAlex 一次最多查 50 个 id
REQ_PER_SEC = 10  # 限速
PROGRESS_FILE = ".abstract_progress.json"


# ===========================


def make_session() -> requests.Session:
    """创建带重试机制的 requests session"""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1,  # 1, 2, 4, 8, 16 秒
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


def reconstruct_abstract(inverted_index: dict) -> str:
    """
    OpenAlex 的 abstract 是倒排索引格式:
        {"machine": [0, 15], "learning": [1, 16], ...}
    需要按位置重组成纯文本。
    """
    if not inverted_index:
        return ""
    positions = {}
    for word, poslist in inverted_index.items():
        for pos in poslist:
            positions[pos] = word
    if not positions:
        return ""
    sorted_positions = sorted(positions.keys())
    return " ".join(positions[i] for i in sorted_positions)


# 在 backfill_abstract.py 中替换 fetch_abstracts_batch 函数
def fetch_abstracts_batch(
        session: requests.Session, paper_ids: List[str]
) -> Dict[str, dict]:
    """
    批量查询一组 paper 的 abstract。
    返回 {paper_id: {"status": "ok"/"no_abstract"/"not_found"/"error", "abstract": str 或 None}}
    """
    short_ids = [pid.replace("https://openalex.org/", "") for pid in paper_ids]
    filter_str = "|".join(short_ids)

    params = {
        "filter": f"openalex:{filter_str}",
        "per-page": BATCH_SIZE,
        "select": "id,abstract_inverted_index",
        "mailto": OPENALEX_MAILTO,
    }

    try:
        resp = session.get(OPENALEX_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"API error for batch starting {short_ids[0]}: {e}")
        return {pid: {"status": "error", "abstract": None} for pid in paper_ids}

    # 初始化：默认 "not_found"（如果 API 没返回这个 id）
    result = {pid: {"status": "not_found", "abstract": None} for pid in paper_ids}

    for work in data.get("results", []):
        paper_id = work.get("id")
        if paper_id not in result:
            continue

        inverted = work.get("abstract_inverted_index")
        if inverted:
            abstract = reconstruct_abstract(inverted)
            result[paper_id] = {"status": "ok", "abstract": abstract}
        else:
            result[paper_id] = {"status": "no_abstract", "abstract": ""}

    return result

class AbstractBackfiller:
    def __init__(self, uri: str, user: str, password: str, database: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def close(self):
        self.driver.close()

    def get_papers_without_abstract(self, limit: Optional[int] = None) -> List[str]:
        """查出所有还没补 abstract 的 Paper id"""
        cypher = """
        MATCH (p:Paper)
        WHERE p.abstract IS NULL
        RETURN p.id AS id
        """
        if limit:
            cypher += f" LIMIT {limit}"

        with self.driver.session(database=self.database) as sess:
            result = sess.run(cypher)
            return [r["id"] for r in result]

    def update_abstracts(self, updates: Dict[str, str]):
        """
        批量回写 abstract 到 Neo4j。
        updates: {paper_id: abstract_text}
        """
        # 过滤掉 None 和空字符串，用空字符串占位避免重复抓取
        batch = [
            {"id": pid, "abstract": abstract if abstract else ""}
            for pid, abstract in updates.items()
        ]

        cypher = """
        UNWIND $batch AS row
        MATCH (p:Paper {id: row.id})
        SET p.abstract = row.abstract
        """
        with self.driver.session(database=self.database) as sess:
            sess.run(cypher, batch=batch)

    def count_with_abstract(self) -> int:
        with self.driver.session(database=self.database) as sess:
            return sess.run(
                "MATCH (p:Paper) WHERE p.abstract IS NOT NULL AND p.abstract <> '' RETURN count(p) AS c"
            ).single()["c"]

    def count_total(self) -> int:
        with self.driver.session(database=self.database) as sess:
            return sess.run("MATCH (p:Paper) RETURN count(p) AS c").single()["c"]


def load_progress() -> Set[str]:
    if not Path(PROGRESS_FILE).exists():
        return set()
    try:
        with open(PROGRESS_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_progress(processed: Set[str]):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(list(processed), f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Process only N papers (for testing)")
    parser.add_argument("--resume", action="store_true", help="Resume from progress file")
    parser.add_argument("--reset", action="store_true", help="Delete progress file and start over")
    args = parser.parse_args()

    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    if OPENALEX_MAILTO == "your_email@example.com":
        logger.warning("⚠️  请先修改脚本顶部的 OPENALEX_MAILTO 为你的邮箱")
        response = input("要继续用默认邮箱跑吗（会用匿名池，速率较慢）？输入 yes 继续: ")
        if response.strip().lower() != "yes":
            sys.exit(0)

    if args.reset and Path(PROGRESS_FILE).exists():
        Path(PROGRESS_FILE).unlink()
        logger.info("Progress file deleted.")

    backfiller = AbstractBackfiller(uri, user, password, database)
    http = make_session()

    try:
        # 获取需要处理的 paper ids
        total_in_db = backfiller.count_total()
        already_done = backfiller.count_with_abstract()
        logger.info(f"Database status: {already_done}/{total_in_db} papers have abstracts")

        all_pending = backfiller.get_papers_without_abstract(limit=args.limit)
        logger.info(f"Papers to process: {len(all_pending)}")

        if not all_pending:
            logger.info("✅ All papers already have abstracts. Nothing to do.")
            return

        # 加载进度
        processed: Set[str] = load_progress() if args.resume else set()
        if processed:
            all_pending = [p for p in all_pending if p not in processed]
            logger.info(f"Resuming: {len(processed)} already done, {len(all_pending)} remaining")

        # 批量处理
        pbar = tqdm(total=len(all_pending), desc="Backfilling abstracts")
        stats = {
            "with_abstract": 0,
            "no_abstract": 0,
            "not_found": 0,
            "errors": 0,
        }

        for i in range(0, len(all_pending), BATCH_SIZE):
            batch_ids = all_pending[i: i + BATCH_SIZE]

            t_start = time.time()
            batch_result = fetch_abstracts_batch(http, batch_ids)

            # 按状态分类统计 + 准备写入
            updates_for_neo4j = {}
            for pid, info in batch_result.items():
                status = info["status"]
                if status == "ok":
                    stats["with_abstract"] += 1
                    updates_for_neo4j[pid] = info["abstract"]
                elif status == "no_abstract":
                    stats["no_abstract"] += 1
                    # 写入空字符串，标记"已处理但无内容"，避免下次重复查
                    updates_for_neo4j[pid] = ""
                elif status == "not_found":
                    stats["not_found"] += 1
                    # 不写入，下次可以重试
                elif status == "error":
                    stats["errors"] += 1
                    # 不写入，下次可以重试

            # 写入 Neo4j（只写成功和确认无 abstract 的）
            if updates_for_neo4j:
                try:
                    backfiller.update_abstracts(updates_for_neo4j)
                except Exception as e:
                    logger.error(f"Neo4j write error: {e}")

            # 更新进度
            processed.update(batch_ids)
            if i % (BATCH_SIZE * 10) == 0:
                save_progress(processed)

            pbar.update(len(batch_ids))

            # 限速
            elapsed = time.time() - t_start
            min_interval = 1.0 / REQ_PER_SEC
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)

        pbar.close()
        save_progress(processed)

        # 最终统计
        logger.info("\n=== Final Statistics ===")
        logger.info(f"  ✅ 有 abstract:           {stats['with_abstract']}")
        logger.info(f"  ⚪ 无 abstract (OA 确认): {stats['no_abstract']}")
        logger.info(f"  ❓ OA 未找到:             {stats['not_found']}")
        logger.info(f"  ❌ API/网络错误:          {stats['errors']}")

        final_with_abstract = backfiller.count_with_abstract()
        logger.info(f"\n📊 数据库状态: {final_with_abstract}/{total_in_db} papers 有 abstract")

    finally:
        backfiller.close()


if __name__ == "__main__":
    main()