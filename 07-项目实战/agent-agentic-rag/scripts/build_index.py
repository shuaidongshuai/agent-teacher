#!/usr/bin/env python3
"""
构建知识库索引。

运行方式:
    python scripts/build_index.py

首次运行会自动下载 BGE embedding 模型（~90MB）。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import AgenticRAGConfig
from app.knowledge_base import KnowledgeBase


def main() -> int:
    config = AgenticRAGConfig(
        project_root=PROJECT_ROOT,
        data_dir=PROJECT_ROOT / "data",
    )

    print("正在构建知识库索引...")
    kb = KnowledgeBase.from_data(config.data_dir, config)
    print(f"索引构建完成！共 {len(kb.hybrid.vector_store.chunks)} 个 chunk")
    return 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    raise SystemExit(main())
