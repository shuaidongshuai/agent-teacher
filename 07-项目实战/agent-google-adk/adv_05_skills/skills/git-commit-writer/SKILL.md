---
name: git-commit-writer
description: 写规范的 Git commit message（Conventional Commits 风格）。当用户要写或修改提交信息时使用。
allowed_tools: Bash
---

# 写规范的 Git 提交信息

1. 先看改动：`git diff --staged`
2. 判断类型：feat / fix / docs / refactor / test / chore
3. 按格式输出：`<type>(<scope>): <简洁标题>`，标题不超过 50 字、用祈使句
4. 需要时空一行写正文，重点说明「为什么」而不仅是「改了什么」
5. 标题结尾不要加句号
