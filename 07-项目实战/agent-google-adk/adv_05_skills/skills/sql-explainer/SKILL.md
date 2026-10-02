---
name: sql-explainer
description: 解释一条 SQL 在做什么，并指出潜在性能问题。当用户贴出 SQL 求解释或优化时使用。
---

# 解释与优化 SQL

1. 逐子句拆解：SELECT / FROM / JOIN / WHERE / GROUP BY / ORDER BY 各自的作用
2. 用一句话总结「这条 SQL 到底想取什么数据」
3. 检查性能红旗：全表扫描、`SELECT *`、过滤列缺索引、N+1、隐式类型转换
4. 给出 1~3 条可执行的优化建议
