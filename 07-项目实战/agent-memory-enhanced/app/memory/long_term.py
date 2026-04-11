from __future__ import annotations

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryEntry:
    """一条长期记忆。"""

    def __init__(
        self,
        content: str,
        category: str = "other",
        timestamp: Optional[str] = None,
        source_turn: int = 0,
    ) -> None:
        self.content = content
        self.category = category
        self.timestamp = timestamp or datetime.now().isoformat()
        self.source_turn = source_turn

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "category": self.category,
            "timestamp": self.timestamp,
            "source_turn": self.source_turn,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemoryEntry":
        return cls(
            content=d["content"],
            category=d.get("category", "other"),
            timestamp=d.get("timestamp"),
            source_turn=d.get("source_turn", 0),
        )


class LongTermMemory:
    """
    长期记忆：FAISS 语义检索 + JSON 持久化。

    每条记忆编码为向量存入 FAISS，同时保存到 JSON 文件。
    检索时用 BGE embedding 的语义相似度返回最相关的记忆。
    """

    def __init__(
        self,
        storage_dir: Path,
        embedding_model_name: str = "BAAI/bge-small-zh-v1.5",
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_model_name = embedding_model_name

        self._embedder = None
        self._index = None
        self.entries: List[MemoryEntry] = []

        # 尝试加载已有记忆
        self._load()

    def _get_embedder(self):
        """懒加载 embedding 模型。"""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("加载 embedding 模型: %s", self.embedding_model_name)
                self._embedder = SentenceTransformer(self.embedding_model_name)
            except ImportError:
                logger.warning(
                    "sentence-transformers 未安装，长期记忆的语义检索不可用"
                )
        return self._embedder

    def _get_index(self):
        """懒加载或创建 FAISS 索引。"""
        if self._index is not None:
            return self._index

        embedder = self._get_embedder()
        if embedder is None:
            return None

        try:
            import faiss
            import numpy as np

            dim = embedder.get_sentence_embedding_dimension()

            index_path = self.storage_dir / "memory.faiss"
            if index_path.exists() and self.entries:
                self._index = faiss.read_index(str(index_path))
            else:
                self._index = faiss.IndexFlatIP(dim)

            return self._index
        except ImportError:
            logger.warning("faiss 未安装，长期记忆的向量检索不可用")
            return None

    def store(self, content: str, category: str = "other", source_turn: int = 0) -> None:
        """存储一条新记忆。"""
        entry = MemoryEntry(
            content=content,
            category=category,
            source_turn=source_turn,
        )
        self.entries.append(entry)

        # 添加到 FAISS 索引
        embedder = self._get_embedder()
        index = self._get_index()
        if embedder is not None and index is not None:
            import numpy as np
            vec = embedder.encode([content], normalize_embeddings=True)
            index.add(np.array(vec, dtype=np.float32))

        # 持久化
        self._save()
        logger.info("已存储记忆: [%s] %s", category, content[:50])

    def recall(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """语义检索最相关的记忆。"""
        if not self.entries:
            return []

        embedder = self._get_embedder()
        index = self._get_index()

        if embedder is None or index is None or index.ntotal == 0:
            # 回退：关键词匹配
            return self._keyword_recall(query, top_k)

        import numpy as np

        # BGE 检索前缀
        prefixed = f"为这个句子生成表示以用于检索中文文档：{query}"
        query_vec = embedder.encode([prefixed], normalize_embeddings=True)
        query_vec = np.array(query_vec, dtype=np.float32)

        actual_k = min(top_k, index.ntotal)
        scores, indices = index.search(query_vec, actual_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if 0 <= idx < len(self.entries) and score > 0.3:
                results.append(self.entries[idx])

        return results

    def _keyword_recall(self, query: str, top_k: int) -> List[MemoryEntry]:
        """关键词回退检索。"""
        scored = []
        query_lower = query.lower()
        for entry in self.entries:
            content_lower = entry.content.lower()
            # 简单计算重叠字符数
            overlap = sum(1 for c in query_lower if c in content_lower)
            scored.append((entry, overlap))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [entry for entry, _ in scored[:top_k]]

    def _save(self) -> None:
        """持久化到磁盘。"""
        # 保存 JSON
        json_path = self.storage_dir / "memories.json"
        data = [e.to_dict() for e in self.entries]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 保存 FAISS 索引
        if self._index is not None and self._index.ntotal > 0:
            import faiss
            faiss.write_index(self._index, str(self.storage_dir / "memory.faiss"))

    def _load(self) -> None:
        """从磁盘加载。"""
        json_path = self.storage_dir / "memories.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [MemoryEntry.from_dict(d) for d in data]
            logger.info("已加载 %d 条长期记忆", len(self.entries))

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有记忆条目。"""
        return [e.to_dict() for e in self.entries]

    def clear(self) -> None:
        """清空所有记忆。"""
        self.entries.clear()
        self._index = None
        # 删除磁盘文件
        for f in self.storage_dir.glob("memory.*"):
            f.unlink()
        json_path = self.storage_dir / "memories.json"
        if json_path.exists():
            json_path.unlink()
