#!/usr/bin/env python3
"""Check first-run dependencies, corpus DB, and embedding model readiness."""

from __future__ import annotations

import importlib.util
import os
import sqlite3
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_ID = "BAAI/bge-small-zh-v1.5"
RELEASE_MODEL_URL = (
    "https://github.com/hellowinter2025/zhouli-commentary/releases/latest/download/"
    "bge-small-zh-v1.5.zip"
)
LOCAL_MODEL_CANDIDATES = (
    SKILL_DIR / "models" / "bge-small-zh-v1.5",
    SKILL_DIR / "models" / "BAAI" / "bge-small-zh-v1.5",
)
DB_CANDIDATES = (
    SKILL_DIR / "data" / "poetry_embeddings.sqlite",
    SKILL_DIR.parent / "data" / "rag" / "poetry_embeddings.sqlite",
)


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def bad(msg: str) -> None:
    print(f"[FAIL] {msg}")


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def is_local_model_dir(path: Path) -> bool:
    return path.is_dir() and (path / "config.json").is_file()


def find_db() -> Path | None:
    env_path = os.environ.get("ZHOU_LI_RAG_DB")
    candidates = []
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(DB_CANDIDATES)
    for item in candidates:
        if item.is_file():
            return item.resolve()
    return None


def find_local_model() -> Path | None:
    env_path = os.environ.get("ZHOU_LI_EMBED_MODEL_PATH")
    candidates = []
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(LOCAL_MODEL_CANDIDATES)
    for item in candidates:
        if is_local_model_dir(item):
            return item.resolve()
    return None


def hf_cache_ready(model_id: str = DEFAULT_MODEL_ID) -> bool:
    try:
        from transformers import AutoModel, AutoTokenizer
    except Exception:
        return False
    try:
        AutoTokenizer.from_pretrained(model_id, local_files_only=True)
        AutoModel.from_pretrained(model_id, local_files_only=True)
        return True
    except Exception:
        return False


def main() -> int:
    configure_stdio()
    failures = 0
    print(f"skill_dir={SKILL_DIR}")
    print(f"python={sys.executable}")
    print(f"version={sys.version.split()[0]}")
    print()

    for name, import_name in (
        ("numpy", "numpy"),
        ("opencc-python-reimplemented", "opencc"),
        ("torch", "torch"),
        ("transformers", "transformers"),
    ):
        if has_module(import_name):
            try:
                mod = __import__(import_name)
                version = getattr(mod, "__version__", "unknown")
                ok(f"{name} ({version})")
            except Exception as exc:  # noqa: BLE001
                bad(f"{name} 已安装但导入失败：{exc}")
                failures += 1
        else:
            bad(f"缺少 {name}")
            failures += 1

    if failures:
        print()
        print("安装依赖：")
        print("  python -m pip install -U pip")
        print(f'  python -m pip install -r "{SKILL_DIR / "requirements.txt"}"')
        print("Windows 也可：")
        print(
            f'  powershell -ExecutionPolicy Bypass -File "{SKILL_DIR / "scripts" / "setup_windows.ps1"}"'
        )

    print()
    db = find_db()
    if db is None:
        bad("找不到 poetry_embeddings.sqlite")
        failures += 1
    else:
        try:
            with sqlite3.connect(db) as conn:
                model = conn.execute("select value from meta where key='model'").fetchone()
                count = conn.execute("select count(*) from chunks").fetchone()[0]
            ok(f"数据库 {db} （chunks={count}, model={model[0] if model else 'missing'}）")
            if not model:
                bad("数据库缺少 meta.model")
                failures += 1
        except Exception as exc:  # noqa: BLE001
            bad(f"数据库无法读取：{exc}")
            failures += 1

    print()
    local_model = find_local_model()
    if local_model is not None:
        ok(f"本地模型目录可用：{local_model}")
    elif hf_cache_ready():
        ok(f"Hugging Face 本地缓存可用：{DEFAULT_MODEL_ID}")
    else:
        warn(f"尚未准备好本地模型；首次检索会尝试从 Hugging Face 下载 {DEFAULT_MODEL_ID}")
        warn(f"备份包：{RELEASE_MODEL_URL}")
        warn(f"解压目标：{SKILL_DIR / 'models' / 'bge-small-zh-v1.5'}")

    print()
    if failures:
        bad(f"检查未通过，失败项={failures}")
        print("查看完整安装说明：")
        print(f'  python "{SKILL_DIR / "scripts" / "search_classics.py"}" --print-setup-hint')
        return 1

    ok("基础环境检查通过。可直接运行 search_classics.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
