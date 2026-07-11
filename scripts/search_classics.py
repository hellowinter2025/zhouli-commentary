#!/usr/bin/env python3
"""Search the bundled classical Chinese embedding database."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import numpy as np


SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_CANDIDATES = (
    SKILL_DIR / "data" / "poetry_embeddings.sqlite",
    SKILL_DIR.parent / "data" / "rag" / "poetry_embeddings.sqlite",
)


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def find_database(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_path = os.environ.get("ZHOU_LI_RAG_DB")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(DEFAULT_DB_CANDIDATES)

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved

    searched = "\n".join(f"  - {item.resolve()}" for item in candidates)
    raise SystemExit(f"找不到向量数据库，已检查：\n{searched}")


def to_simplified(text: str) -> str:
    try:
        from opencc import OpenCC
    except ImportError as exc:
        raise SystemExit("缺少 opencc-python-reimplemented，请安装 requirements.txt") from exc
    return OpenCC("t2s").convert(text)


class Embedder:
    def __init__(self, model_name: str, batch_size: int = 16):
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise SystemExit("缺少 torch 或 transformers，请安装 requirements.txt") from exc

        self.torch = torch
        self.batch_size = batch_size
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
            self.model = AutoModel.from_pretrained(model_name, local_files_only=True)
        except OSError:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors: list[np.ndarray] = []
        with self.torch.inference_mode():
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start : start + self.batch_size]
                encoded = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                )
                output = self.model(**encoded)
                token_embeddings = output.last_hidden_state
                mask = encoded["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
                pooled = (token_embeddings * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                pooled = self.torch.nn.functional.normalize(pooled, p=2, dim=1)
                vectors.append(pooled.cpu().numpy().astype("float32"))
        return np.vstack(vectors)


def load_database(db_path: Path) -> tuple[str, list[dict], np.ndarray]:
    with sqlite3.connect(db_path) as conn:
        model_row = conn.execute("select value from meta where key = 'model'").fetchone()
        if not model_row:
            raise SystemExit("数据库缺少 meta.model，无法确定嵌入模型")
        rows = conn.execute(
            """
            select id, work, chapter, section, title, paragraph_index,
                   part_index, text, metadata_json, dim, vector
            from chunks
            """
        ).fetchall()

    if not rows:
        raise SystemExit("数据库中没有可检索的句子")

    records: list[dict] = []
    vectors: list[np.ndarray] = []
    for row in rows:
        metadata = json.loads(row[8])
        records.append(
            {
                "id": row[0],
                "work": row[1],
                "chapter": row[2],
                "section": row[3],
                "title": row[4],
                "paragraph_index": row[5],
                "part_index": row[6],
                "text": row[7],
                "metadata": metadata,
            }
        )
        vectors.append(np.frombuffer(row[10], dtype="float32", count=row[9]))
    return model_row[0], records, np.vstack(vectors)


def search(
    queries: list[str],
    records: list[dict],
    matrix: np.ndarray,
    embedder: Embedder,
    top_k: int,
    max_per_work: int,
    min_score: float,
) -> list[dict]:
    clean_queries = [to_simplified(query.strip()) for query in queries if query.strip()]
    query_vectors = embedder.encode(clean_queries)
    score_matrix = matrix @ query_vectors.T
    query_orders = [np.argsort(score_matrix[:, index])[::-1] for index in range(score_matrix.shape[1])]
    query_positions = [0] * len(query_orders)
    results: list[dict] = []
    work_counts: dict[str, int] = {}
    seen_indexes: set[int] = set()
    active_queries = set(range(len(query_orders)))

    # Take candidates round-robin from each semantic angle. This preserves the
    # best focused result even when a broad event description has higher scores.
    while len(results) < top_k and active_queries:
        made_progress = False
        for query_index in list(active_queries):
            order = query_orders[query_index]
            while query_positions[query_index] < len(order):
                index = int(order[query_positions[query_index]])
                query_positions[query_index] += 1
                score = float(score_matrix[index, query_index])
                if score < min_score:
                    active_queries.discard(query_index)
                    break
                if index in seen_indexes:
                    continue

                record = records[index]
                work = record["work"]
                if work_counts.get(work, 0) >= max_per_work:
                    continue

                seen_indexes.add(index)
                work_counts[work] = work_counts.get(work, 0) + 1
                location = " / ".join(
                    part
                    for part in [record["work"], record["chapter"], record["section"], record["title"]]
                    if part
                )
                results.append(
                    {
                        "rank": len(results) + 1,
                        "score": round(score, 6),
                        "matched_query": clean_queries[query_index],
                        "text": record["text"],
                        "work": record["work"],
                        "location": location,
                        "paragraph_index": record["paragraph_index"],
                        "part_index": record["part_index"],
                        "source_path": record["metadata"].get("source_path", ""),
                    }
                )
                made_progress = True
                break
            else:
                active_queries.discard(query_index)

            if len(results) >= top_k:
                break
        if not made_progress:
            break
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", required=True, help="可重复使用，以便一次检索多个语义角度")
    parser.add_argument("--db", help="SQLite 数据库路径；默认自动查找或读取 ZHOU_LI_RAG_DB")
    parser.add_argument("--model", help="覆盖数据库记录的模型名称，通常不应设置")
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-per-work", type=int, default=4)
    parser.add_argument("--min-score", type=float, default=-1.0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--json", action="store_true", help="输出 UTF-8 JSON")
    return parser.parse_args()


def main() -> None:
    configure_stdio()
    args = parse_args()
    if args.top_k < 1 or args.max_per_work < 1:
        raise SystemExit("--top-k 和 --max-per-work 必须大于 0")

    db_path = find_database(args.db)
    db_model, records, matrix = load_database(db_path)
    model_name = args.model or db_model
    embedder = Embedder(model_name, batch_size=args.batch_size)
    results = search(
        queries=args.query,
        records=records,
        matrix=matrix,
        embedder=embedder,
        top_k=args.top_k,
        max_per_work=args.max_per_work,
        min_score=args.min_score,
    )

    if args.json:
        payload = {
            "queries": args.query,
            "model": model_name,
            "database": str(db_path),
            "results": results,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for item in results:
        print(f"#{item['rank']} score={item['score']:.4f} {item['location']}")
        print(item["text"])
        print()


if __name__ == "__main__":
    main()
