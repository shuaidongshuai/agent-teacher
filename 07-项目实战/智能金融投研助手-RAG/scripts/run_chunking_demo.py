#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.embeddings.simple_embedding import SimpleEmbeddingModel
from app.ingest.chunker import SemanticChunker
from app.ingest.cleaner import FinancialDocCleaner
from app.ingest.models import Block


def load_sample_blocks() -> list[Block]:
    sample_path = PROJECT_ROOT / "data" / "sample_blocks.json"
    raw = json.loads(sample_path.read_text(encoding="utf-8"))
    return [Block(**item) for item in raw]


def main() -> int:
    print("=== 智能金融投研助手：数据清洗与语义切片 Demo ===")

    raw_blocks = load_sample_blocks()
    print(f"原始 block 数量：{len(raw_blocks)}")

    cleaner = FinancialDocCleaner()
    cleaned_blocks = cleaner.clean_blocks(raw_blocks)
    print(f"清洗后 block 数量：{len(cleaned_blocks)}")

    chunker = SemanticChunker(
        embedding_model=SimpleEmbeddingModel(dim=16),
        similarity_threshold=0.75,
        max_chars=500,
        min_chars=60,
    )

    chunks = chunker.chunk(cleaned_blocks)
    print(f"最终 chunk 数量：{len(chunks)}")
    print()

    for chunk in chunks:
        print("=" * 70)
        print(f"chunk_id: {chunk.chunk_id}")
        print(f"page_span: {chunk.page_span}")
        print(f"section_path: {' > '.join(chunk.section_path) if chunk.section_path else '(无)'}")
        print(f"metadata: {json.dumps(chunk.metadata, ensure_ascii=False)}")
        print("content:")
        print(chunk.content)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
