# PBH arXiv Daily（原初黑洞每日 arXiv 追踪）

## 中文说明

### 1. 项目简介
本项目用于每天抓取 arXiv 的 `gr-qc/new` 与 `astro-ph/new`（可自行修改），在“New submissions + Cross-lists”中检索与原初黑洞(PBH)相关的条目，并生成：
- 当天批次的结构化 JSON 归档（永久保存）
- 一个可公开访问的静态网页，展示当天匹配结果、作者信息、以及累计统计

本项目不依赖本地电脑常驻运行：由 GitHub Actions 定时触发并在云端执行。

---

### 2. 功能特性
- **自动抓取**：抓取 arXiv 列表页（/new）并解析条目
- **关键词匹配**：匹配 PBH(s) / primordial black hole(s) 等关键词（可配置）
- **过滤 replaced**：不统计 “replaced” 条目
- **按批次日期归档**：以 arXiv 页面显示的 “Showing new listings for …” 日期为批次日期
  - 如果当天 arXiv 不更新，则不产生新批次、不写新数据
- **静态网页展示**：
  - 当日匹配列表（默认隐藏作者，按钮一键显示/隐藏）
  - 归档链接（默认展示最近 30 次更新批次的 JSON）
  - Top 作者（累计匹配次数）
  - 支持作者筛选（如你启用了对应按钮/交互逻辑）

---

### 3. 核心配置
在 `scripts/pbh_watch.py` 中配置搜索的范围，我这里搜的是astro-ph和gr-qc：
```python
LIST_PAGES = {
  "astro-ph": "https://arxiv.org/list/astro-ph/new",
  "gr-qc": "https://arxiv.org/list/gr-qc/new",
}

