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
DEFAULT_MODEL_ID = "BAAI/bge-small-zh-v1.5"
DEFAULT_DB_CANDIDATES = (
    SKILL_DIR / "data" / "poetry_embeddings.sqlite",
    SKILL_DIR.parent / "data" / "rag" / "poetry_embeddings.sqlite",
)
DEFAULT_LOCAL_MODEL_CANDIDATES = (
    SKILL_DIR / "models" / "bge-small-zh-v1.5",
    SKILL_DIR / "models" / "BAAI" / "bge-small-zh-v1.5",
)
RELEASE_MODEL_URL = (
    "https://github.com/hellowinter2025/zhouli-commentary/releases/latest/download/"
    "bge-small-zh-v1.5.zip"
)
HF_MODEL_PAGE = "https://huggingface.co/BAAI/bge-small-zh-v1.5"
SETUP_HINT = f"""首次使用请先完成依赖与模型准备：

1) 安装 Python 依赖（推荐在 skill 目录下执行）：
   python -m pip install -U pip
   python -m pip install -r "{SKILL_DIR / 'requirements.txt'}"

   Windows 也可运行：
   powershell -ExecutionPolicy Bypass -File "{SKILL_DIR / 'scripts' / 'setup_windows.ps1'}"

2) 准备嵌入模型 {DEFAULT_MODEL_ID}（约 92 MB）
   主路径：首次运行本脚本时自动从 Hugging Face 下载并缓存
   备份路径：从 GitHub Release 下载并解压到 skill 的 models 目录
     {RELEASE_MODEL_URL}
     解压后应存在：
     {SKILL_DIR / 'models' / 'bge-small-zh-v1.5' / 'config.json'}

3) 检查环境：
   python "{SKILL_DIR / 'scripts' / 'check_setup.py'}"

模型页：{HF_MODEL_PAGE}
"""


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def is_local_model_dir(path: Path) -> bool:
    return path.is_dir() and (path / "config.json").is_file()


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
    raise SystemExit(f"找不到向量数据库，已检查：\n{searched}\n\n{SETUP_HINT}")


def resolve_model_source(explicit_model: str | None, explicit_path: str | None) -> str:
    """Return a transformers-compatible model id or local directory path."""
    if explicit_path:
        path = Path(explicit_path).expanduser().resolve()
        if not is_local_model_dir(path):
            raise SystemExit(
                f"--model-path 不是有效的本地模型目录（需要 config.json）：{path}\n\n{SETUP_HINT}"
            )
        return str(path)

    env_path = os.environ.get("ZHOU_LI_EMBED_MODEL_PATH")
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if is_local_model_dir(path):
            return str(path)
        raise SystemExit(
            f"环境变量 ZHOU_LI_EMBED_MODEL_PATH 无效（需要含 config.json 的目录）：{path}\n\n{SETUP_HINT}"
        )

    for candidate in DEFAULT_LOCAL_MODEL_CANDIDATES:
        if is_local_model_dir(candidate):
            return str(candidate.resolve())

    if explicit_model:
        path = Path(explicit_model).expanduser()
        if is_local_model_dir(path):
            return str(path.resolve())
        return explicit_model

    env_model = os.environ.get("ZHOU_LI_EMBED_MODEL")
    if env_model:
        path = Path(env_model).expanduser()
        if is_local_model_dir(path):
            return str(path.resolve())
        return env_model

    return DEFAULT_MODEL_ID


def to_simplified(text: str) -> str:
    try:
        from opencc import OpenCC
    except ImportError as exc:
        raise SystemExit(
            "缺少 opencc-python-reimplemented。\n"
            f'请执行：python -m pip install -r "{SKILL_DIR / "requirements.txt"}"\n\n'
            f"{SETUP_HINT}"
        ) from exc
    return OpenCC("t2s").convert(text)


class Embedder:
    def __init__(self, model_source: str, batch_size: int = 16):
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise SystemExit(
                "缺少 torch 或 transformers。\n"
                f'请执行：python -m pip install -r "{SKILL_DIR / "requirements.txt"}"\n\n'
                f"{SETUP_HINT}"
            ) from exc

        self.torch = torch
        self.batch_size = batch_size
        self.model_source = model_source
        self.tokenizer, self.model = self._load_model(AutoTokenizer, AutoModel, model_source)
        self.model.eval()

    @staticmethod
    def _load_model(auto_tokenizer, auto_model, model_source: str):
        local_dir = Path(model_source)
        if local_dir.is_dir():
            try:
                tokenizer = auto_tokenizer.from_pretrained(str(local_dir), local_files_only=True)
                model = auto_model.from_pretrained(str(local_dir), local_files_only=True)
                return tokenizer, model
            except OSError as exc:
                raise SystemExit(
                    f"本地模型目录无法加载：{local_dir}\n"
                    "请确认已完整解压 Release 中的 bge-small-zh-v1.5.zip。\n\n"
                    f"{SETUP_HINT}"
                ) from exc

        # Hugging Face model id: prefer local hub cache, then online download.
        try:
            tokenizer = auto_tokenizer.from_pretrained(model_source, local_files_only=True)
            model = auto_model.from_pretrained(model_source, local_files_only=True)
            return tokenizer, model
        except OSError:
            pass

        print(
            f"本地未找到模型缓存，开始从 Hugging Face 下载：{model_source}",
            file=sys.stderr,
        )
        print(
            "若下载失败，可改用 GitHub Release 备份："
            f"{RELEASE_MODEL_URL}",
            file=sys.stderr,
        )
        try:
            tokenizer = auto_tokenizer.from_pretrained(model_source)
            model = auto_model.from_pretrained(model_source)
            return tokenizer, model
        except Exception as exc:  # noqa: BLE001 - surface actionable setup help
            raise SystemExit(
                f"无法加载嵌入模型：{model_source}\n"
                f"原因：{exc}\n\n"
                "可访问 GitHub 的机器通常也能访问 Hugging Face；"
                "若暂时失败，请使用 Release 备份模型包：\n"
                f"  {RELEASE_MODEL_URL}\n"
                f"解压到：{SKILL_DIR / 'models' / 'bge-small-zh-v1.5'}\n\n"
                f"{SETUP_HINT}"
            ) from exc

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
    parser.add_argument("--query", action="append", help="可重复使用，以便一次检索多个语义角度")
    parser.add_argument("--db", help="SQLite 数据库路径；默认自动查找或读取 ZHOU_LI_RAG_DB")
    parser.add_argument(
        "--model",
        help="覆盖数据库记录的模型名称或本地模型目录；通常只需使用本地 models/ 或 Hugging Face 默认值",
    )
    parser.add_argument(
        "--model-path",
        help="本地模型目录（含 config.json）；优先于 --model 与环境变量中的模型名",
    )
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--max-per-work", type=int, default=4)
    parser.add_argument("--min-score", type=float, default=-1.0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--json", action="store_true", help="输出 UTF-8 JSON")
    parser.add_argument(
        "--print-setup-hint",
        action="store_true",
        help="打印首次安装依赖与模型的说明后退出",
    )
    return parser.parse_args()


def main() -> None:
    configure_stdio()
    args = parse_args()
    if args.print_setup_hint:
        print(SETUP_HINT)
        return
    if not args.query:
        raise SystemExit("请至少提供一个 --query；查看安装说明可用 --print-setup-hint")
    if args.top_k < 1 or args.max_per_work < 1:
        raise SystemExit("--top-k 和 --max-per-work 必须大于 0")

    db_path = find_database(args.db)
    db_model, records, matrix = load_database(db_path)
    model_source = resolve_model_source(args.model or db_model, args.model_path)
    embedder = Embedder(model_source, batch_size=args.batch_size)
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
            "model": model_source,
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