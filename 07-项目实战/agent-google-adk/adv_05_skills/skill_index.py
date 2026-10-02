"""生产级本地 Skill 索引：L1 常驻内存 + L2 懒加载 + 向量落盘缓存 + 增量嵌入。

相比"全量加载+每次启动重算 embedding+全量正文常驻内存"，这里做了三件生产必做的事：

1. **只常驻 L1**：内存里只放 name+description（+可选向量）。检索用 L1；
   正文(L2)在命中 load_body(name) 时**才从磁盘读**——正文再多再大也不占内存。
2. **向量落盘缓存 + 增量嵌入**：向量按 内容 hash 缓存到 skill_vectors.json。
   启动时命中缓存的 skill **不重算**；只有新增/改动的才调嵌入。
   → 缓存全热时启动**零嵌入调用**（连正文都不读）。
3. **优雅降级**：嵌入后端不可用/离线时回退关键词，始终可跑。

启用向量检索：ADK_SKILL_EMBEDDING=1（需凭证；查询时也要算 query 向量）。
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Optional

from google.adk.skills import list_skills_in_dir, load_skill_from_dir
from google.adk.skills.models import Frontmatter, Skill

_EMBED_MODEL = os.environ.get("ADK_EMBED_MODEL", "text-embedding-004")


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SkillIndex:
    """L1 常驻 + L2 懒加载的技能检索器。"""

    def __init__(self, skills_dir, use_embeddings: bool = False):
        self.skills_dir = Path(skills_dir).resolve()
        # L1：只读 frontmatter（name/description），不含正文/资源
        self._fm: dict[str, Frontmatter] = list_skills_in_dir(self.skills_dir)
        self._cache_path = self.skills_dir.parent / "skill_vectors.json"
        self.mode = "keyword"
        self.embed_error: Optional[str] = None
        self.reembedded = 0  # 本次启动实际(重新)嵌入了几个
        self._vecs: dict[str, list[float]] = {}
        self._client = None
        if use_embeddings:
            self._build_embeddings()

    @property
    def names(self) -> list[str]:
        return list(self._fm)

    # ---------- 向量：落盘缓存 + 增量嵌入 ----------
    def _load_cache(self) -> dict:
        if self._cache_path.exists():
            try:
                return json.loads(self._cache_path.read_text("utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def _build_embeddings(self) -> None:
        try:
            from google import genai

            self._client = genai.Client()  # 查询时也要用它算 query 向量
        except Exception as e:
            self.embed_error = f"client 初始化失败: {e}"
            return  # 保持 keyword

        cache = self._load_cache()
        new_cache, to_embed = {}, []
        for name, fm in self._fm.items():
            text = f"{name}: {fm.description}"
            h = _sha(text)
            hit = cache.get(name)
            if hit and hit.get("hash") == h:  # 命中缓存 → 不重算
                self._vecs[name] = hit["vector"]
                new_cache[name] = hit
            else:
                to_embed.append((name, text, h))

        if to_embed:  # 只对新增/改动的算
            try:
                fresh = self._embed([t for _, t, _ in to_embed], "RETRIEVAL_DOCUMENT")
            except Exception as e:
                self.embed_error = f"文档嵌入失败: {e}"
                return  # 冷缓存又嵌入失败 → 整体退回 keyword
            for (name, _t, h), v in zip(to_embed, fresh):
                self._vecs[name] = v
                new_cache[name] = {"hash": h, "vector": v}

        self.reembedded = len(to_embed)
        if new_cache != cache:
            self._cache_path.write_text(json.dumps(new_cache, ensure_ascii=False), "utf-8")
        self.mode = "embedding"

    def _embed(self, texts: list[str], task: str) -> list[list[float]]:
        from google.genai import types

        resp = self._client.models.embed_content(
            model=_EMBED_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task),
        )
        return [e.values for e in resp.embeddings]

    def _keyword_scored(self, query: str) -> list[tuple[float, Frontmatter]]:
        q = query.lower()
        out = []
        for name, fm in self._fm.items():
            keys = name.lower().replace("-", " ").split() + fm.description.lower().split()
            out.append((float(sum(1 for k in set(keys) if k and k in q)), fm))
        return out

    # ---------- 检索(返回 L1) + 懒加载(L2) ----------
    def search(self, query: str, top_k: int = 5) -> list[Frontmatter]:
        """返回 top-k 个候选的 frontmatter(L1)，不含正文。"""
        if self.mode == "embedding" and self._vecs:
            try:
                qv = self._embed([query], "RETRIEVAL_QUERY")[0]
                scored = [(_cosine(qv, self._vecs[n]), self._fm[n]) for n in self._vecs]
            except Exception:  # 查询时嵌入失败 → 本次退回关键词
                scored = self._keyword_scored(query)
        else:
            scored = self._keyword_scored(query)
        scored = [(s, fm) for s, fm in scored if s > 0]
        scored.sort(key=lambda x: -x[0])
        return [fm for _, fm in scored[:top_k]]

    def load_body(self, name: str) -> Optional[Skill]:
        """命中后才从磁盘读该技能的完整正文/资源(L2)。"""
        d = self.skills_dir / name
        return load_skill_from_dir(str(d)) if d.is_dir() else None
