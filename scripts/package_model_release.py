#!/usr/bin/env python3
"""Package local HF cache of BAAI/bge-small-zh-v1.5 into a Release zip."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def find_snapshot(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"SnapshotDir 不存在：{path}")
        return path

    hub = (
        Path.home()
        / ".cache"
        / "huggingface"
        / "hub"
        / "models--BAAI--bge-small-zh-v1.5"
        / "snapshots"
    )
    if not hub.is_dir():
        raise SystemExit(f"未找到 HF 缓存 snapshots：{hub}\n请先成功加载一次模型。")
    candidates = sorted(
        [p for p in hub.iterdir() if p.is_dir() and (p / "config.json").exists()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise SystemExit("snapshots 下没有可用模型目录")
    return candidates[0]


def resolve_real_file(path: Path) -> Path:
    if path.is_symlink() or path.stat().st_size == 0:
        try:
            target = os.readlink(path)
            real = (path.parent / target).resolve()
            if real.is_file() or real.is_dir():
                return real
        except OSError:
            pass
        try:
            return path.resolve(strict=True)
        except OSError:
            return path
    return path


def materialize_tree(src_dir: Path, dest_dir: Path) -> None:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)
    for item in src_dir.iterdir():
        dest = dest_dir / item.name
        if item.is_dir() and not item.is_symlink():
            materialize_tree(item, dest)
            continue
        real = resolve_real_file(item)
        if real.is_dir():
            shutil.copytree(real, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(real, dest)


def package(snapshot: Path, output_zip: Path) -> None:
    stage_root = SKILL_DIR / "dist" / "_stage_model"
    stage_model = stage_root / "bge-small-zh-v1.5"
    materialize_tree(snapshot, stage_model)

    config = stage_model / "config.json"
    if not config.is_file() or config.stat().st_size == 0:
        raise SystemExit("打包暂存目录缺少有效 config.json")

    weights = list(stage_model.glob("model.safetensors")) + list(
        stage_model.glob("pytorch_model.bin")
    )
    if not weights or weights[0].stat().st_size < 1_000_000:
        sizes = {p.name: p.stat().st_size for p in stage_model.iterdir() if p.is_file()}
        raise SystemExit(f"打包结果缺少有效模型权重。files={sizes}")

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        output_zip.unlink()

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_STORED) as zf:
        for path in stage_model.rglob("*"):
            if path.is_file():
                zf.write(
                    path,
                    arcname=str(Path("bge-small-zh-v1.5") / path.relative_to(stage_model)),
                )

    shutil.rmtree(stage_root)
    mb = output_zip.stat().st_size / (1024 * 1024)
    print(f"packed={output_zip} size_mb={mb:.2f}")
    print("Upload this zip as a GitHub Release asset named bge-small-zh-v1.5.zip")


def main() -> None:
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", default=str(SKILL_DIR / "dist" / "bge-small-zh-v1.5.zip")
    )
    parser.add_argument("--snapshot", default=None)
    args = parser.parse_args()
    snapshot = find_snapshot(args.snapshot)
    print(f"source={snapshot}")
    package(snapshot, Path(args.output).expanduser().resolve())


if __name__ == "__main__":
    main()