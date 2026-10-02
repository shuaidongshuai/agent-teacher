"""离线演示：加载 + top-k 检索本地 Skill（默认关键词，无需 Key）。

  python adv_05_skills/demo.py "帮我写 git commit"
  python adv_05_skills/demo.py "解释这条 SQL 的性能问题"

启用向量检索（需模型凭证）：
  ADK_SKILL_EMBEDDING=1 python adv_05_skills/demo.py "从 pdf 提取表格"
"""

import sys
from pathlib import Path

# 让本脚本无论从哪运行，都能把 adv_05_skills 当包导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adv_05_skills.agent import INDEX, TOP_K


def main(query: str) -> None:
    print(f"技能总数={len(INDEX.names)} | 检索模式={INDEX.mode} | top_k={TOP_K} | 本次重嵌入={INDEX.reembedded}")
    if INDEX.embed_error:
        print(f"(向量后端不可用，已降级关键词：{INDEX.embed_error[:80]})")

    hits = INDEX.search(query, top_k=TOP_K)  # 返回 L1(name+desc)，不含正文
    print(f"\n检索: {query!r}")
    if not hits:
        print("  无匹配技能。")
        return
    for i, fm in enumerate(hits, 1):
        print(f"  {i}. {fm.name} — {fm.description}")

    # 命中后才从磁盘懒加载正文（L2）
    top = INDEX.load_body(hits[0].name)
    print(f"\n懒加载最佳技能 [{top.name}] 的完整说明（L2，此刻才读磁盘）：\n" + "-" * 40)
    print(top.instructions)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "帮我写一条 git commit 提交信息")
