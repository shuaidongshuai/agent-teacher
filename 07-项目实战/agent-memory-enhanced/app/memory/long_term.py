from __future__ import annotations

import json
import logging
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        return cls(
            content=data["content"],
            category=data.get("category", "other"),
            timestamp=data.get("timestamp"),
            source_turn=data.get("source_turn", 0),
        )


class LongTermMemory:
    """
    长期记忆：FAISS 语义检索 + JSON 持久化。

    为兼容 Windows 中文路径，FAISS 索引使用 Python 读写字节，
    避免 `faiss.write_index/read_index` 直接打开路径。
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

        self._load()

    @property
    def _json_path(self) -> Path:
        return self.storage_dir / "memories.json"

    @property
    def _faiss_path(self) -> Path:
        return self.storage_dir / "memory.faiss"

    def _normalize_content(self, content: str) -> str:
        text = content.strip().lower()
        return " ".join(text.split())

    def _entry_key(self, entry: MemoryEntry) -> Tuple[str, str]:
        return (entry.category.strip().lower(), self._normalize_content(entry.content))

    def _is_similar_memory(
        self, content: str, category: str, existing: MemoryEntry
    ) -> bool:
        if category.strip().lower() != existing.category.strip().lower():
            return False

        new_text = self._normalize_content(content)
        old_text = self._normalize_content(existing.content)

        if not new_text or not old_text:
            return False

        if new_text == old_text:
            return True

        if new_text in old_text or old_text in new_text:
            return True

        similarity = SequenceMatcher(None, new_text, old_text).ratio()
        return similarity >= 0.86

    def _deduplicate_entries(self) -> bool:
        unique_entries: List[MemoryEntry] = []

        for entry in self.entries:
            if any(
                self._is_similar_memory(entry.content, entry.category, existing)
                for existing in unique_entries
            ):
                continue
            unique_entries.append(entry)

        changed = len(unique_entries) != len(self.entries)
        self.entries = unique_entries
        return changed

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

    def _build_index_from_entries(self):
        import faiss
        import numpy as np

        embedder = self._get_embedder()
        if embedder is None:
            return None

        dim = embedder.get_sentence_embedding_dimension()
        index = faiss.IndexFlatIP(dim)

        if self.entries:
            texts = [entry.content for entry in self.entries]
            vectors = embedder.encode(texts, normalize_embeddings=True)
            index.add(np.array(vectors, dtype=np.float32))

        return index

    def _get_index(self):
        """懒加载或创建 FAISS 索引。"""
        if self._index is not None:
            return self._index

        embedder = self._get_embedder()
        if embedder is None:
            return None

        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)

            if self._faiss_path.exists() and self.entries:
                self._index = self._read_faiss_index()
                if self._index.ntotal != len(self.entries):
                    logger.warning("FAISS 索引与记忆条目数量不一致，改为重建索引")
                    self._index = self._build_index_from_entries()
                    self._save()
            else:
                self._index = self._build_index_from_entries()

            return self._index
        except ImportError:
            logger.warning("faiss 未安装，长期记忆的向量检索不可用")
            return None

    def _read_faiss_index(self):
        import faiss
        import numpy as np

        raw = self._faiss_path.read_bytes()
        buffer = np.frombuffer(raw, dtype=np.uint8)
        return faiss.deserialize_index(buffer)

    def _write_faiss_index(self) -> None:
        import faiss

        serialized = faiss.serialize_index(self._index)
        self._faiss_path.write_bytes(serialized.tobytes())

    def store(self, content: str, category: str = "other", source_turn: int = 0) -> bool:
        """存储一条新记忆；若重复或近似重复则跳过。"""
        content = content.strip()
        category = category.strip() or "other"

        if not content:
            return False

        if any(
            self._is_similar_memory(content, category, existing)
            for existing in self.entries
        ):
            logger.info("跳过重复记忆 [%s] %s", category, content[:50])
            return False

        entry = MemoryEntry(
            content=content,
            category=category,
            source_turn=source_turn,
        )
        self.entries.append(entry)

        embedder = self._get_embedder()
        index = self._get_index()
        if embedder is not None and index is not None:
            import numpy as np

            vec = embedder.encode([content], normalize_embeddings=True)
            index.add(np.array(vec, dtype=np.float32))

        self._save()
        logger.info("已存储记忆 [%s] %s", category, content[:50])
        return True

    def recall(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """语义检索最相关的记忆。"""
        if not self.entries:
            return []

        embedder = self._get_embedder()
        index = self._get_index()

        if embedder is None or index is None or index.ntotal == 0:
            return self._keyword_recall(query, top_k)

        import numpy as np

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
        """回退到简单关键词检索。"""
        scored = []
        query_lower = query.lower()
        for entry in self.entries:
            content_lower = entry.content.lower()
            overlap = sum(1 for char in query_lower if char in content_lower)
            scored.append((entry, overlap))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [entry for entry, _ in scored[:top_k]]

    def _save(self) -> None:
        """持久化到磁盘。"""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        data = [entry.to_dict() for entry in self.entries]
        with open(self._json_path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

        if self._index is not None and self._index.ntotal > 0:
            self._write_faiss_index()
        elif self._faiss_path.exists():
            self._faiss_path.unlink()

    def _load(self) -> None:
        """从磁盘加载。"""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        if self._json_path.exists():
            with open(self._json_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            self.entries = [MemoryEntry.from_dict(item) for item in data]
            if self._deduplicate_entries():
                logger.info("检测到重复长期记忆，已在加载时自动去重")
                self._index = None
                self._save()
            logger.info("已加载 %d 条长期记忆", len(self.entries))

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有记忆条目。"""
        return [entry.to_dict() for entry in self.entries]

    def clear(self) -> None:
        """清空所有记忆。"""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.entries.clear()
        self._index = None

        for file in self.storage_dir.glob("memory.*"):
            file.unlink()

        if self._json_path.exists():
            self._json_path.unlink()
