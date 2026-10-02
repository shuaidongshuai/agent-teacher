---
name: pdf-table-extract
description: 从 PDF 抽取表格并导出为 CSV。当用户提供 PDF 且要求提表 / 转 CSV 时使用。
allowed_tools: Bash, Read
---

# 从 PDF 抽取表格

1. 用 pdfplumber 打开 PDF，逐页 `page.extract_tables()`
2. 清洗：去空行、合并跨页表头、统一列数
3. 用 csv 模块写出 UTF-8 的 CSV（带 BOM 便于 Excel 打开）
4. 报告：共抽出几张表、每张多少行
