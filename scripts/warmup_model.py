#!/usr/bin/env python3
"""Warm up Hugging Face cache for BAAI/bge-small-zh-v1.5."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        print("缺少 transformers，请先安装 requirements.txt", file=sys.stderr)
        print(exc, file=sys.stderr)
        return 1

    name = "BAAI/bge-small-zh-v1.5"
    print(f"downloading {name}")
    AutoTokenizer.from_pretrained(name)
    AutoModel.from_pretrained(name)
    print("hf_cache_ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
