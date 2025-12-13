import json
import os
import re
from datetime import datetime, timezone
import feedparser

FEEDS = {
    "astro-ph.CO": "https://rss.arxiv.org/rss/astro-ph.CO",
    "gr-qc": "https://rss.arxiv.org/rss/gr-qc",
}

# 关键词：primordial black hole(s) / 你提到的 typo "blck" / PBH(s)
PATTERNS = [
    r"primordial\s+black+holes?",
    r"\bPBHs?\b",
]
REGEX = re.compile("|".join(PATTERNS), re.IGNORECASE)

def is_replacement(entry) -> bool:
    at = (entry.get("arxiv_announce_type") or "").lower()
    if "replace" in at:
        return True
    desc = (entry.get("description") or "").lower()
    return "announce type: replace" in desc

def extract_arxiv_id(entry) -> str:
    desc = entry.get("description", "")
    m = re.search(r"arXiv:(\d{4}\.\d{4,5})(v\d+)?", desc)
    return m.group(1) if m else ""

def matched(entry) -> bool:
    hay = " ".join([
        entry.get("title", ""),
        entry.get("description", ""),   # 含摘要
        entry.get("dc_creator", ""),    # 作者
    ])
    return bool(REGEX.search(hay))

def ensure_dirs():
    os.makedirs("docs/data", exist_ok=True)

def load_archive_index():
    # 用 repo 内已有的 docs/data/*.json 做归档索引
    days = []
    if os.path.isdir("docs/data"):
        for fn in os.listdir("docs/data"):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", fn):
                days.append(fn.replace(".json", ""))
    return sorted(days, reverse=True)

def render_html(today, results, days):
    def esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    items_html = ""
    if not results:
        items_html = "<p>今日无匹配条目。</p>"
    else:
        for r in results:
            items_html += (
                "<div class='item'>"
                f"<div class='id'><b>{esc(r['arxiv_id'])}</b> <span class='cat'>{esc(r['category'])}</span></div>"
                f"<div class='title'><a href='{esc(r['link'])}' target='_blank' rel='noopener'>{esc(r['title'])}</a></div>"
                f"<div class='authors'>{esc(r['authors'])}</div>"
                "</div>"
            )

    archive_links = ""
    for d in days[:30]:  # 首页只显示最近30天链接
        archive_links += f"<li><a href='data/{d}.json' target='_blank' rel='noopener'>{d}.json</a></li>"

    return f"""<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PBH arXiv Daily - {today}</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial; margin: 24px; line-height: 1.5; }}
    .meta {{ color: #555; margin-bottom: 18px; }}
    .item {{ padding: 12px 0; border-bottom: 1px solid #eee; }}
    .id {{ font-size: 14px; }}
    .cat {{ color: #666; margin-left: 8px; }}
    .title {{ font-size: 16px; margin: 6px 0; }}
    .authors {{ font-size: 14px; color: #333; }}
    .cols {{ display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }}
    @media (max-width: 900px) {{ .cols {{ grid-template-columns: 1fr; }} }}
    code {{ background: #f6f8fa; padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>PBH arXiv Daily ({today})</h1>
  <div class="meta">
    来源：<code>astro-ph.CO</code> 与 <code>gr-qc</code> 的 arXiv RSS；规则：匹配关键词（PBH / primordial black hole 等），排除 <code>announce_type</code> 含 <code>replace</code> 的条目。
  </div>

  <div class="cols">
    <div>
      <h2>今日匹配</h2>
      {items_html}
    </div>
    <div>
      <h2>归档（最近30天 JSON）</h2>
      <ul>{archive_links}</ul>
      <p style="color:#666;font-size:13px">说明：JSON 里保留 arXiv 号、标题、作者、分类与链接，便于二次处理。</p>
    </div>
  </div>
</body>
</html>
"""

def main():
    ensure_dirs()
    today = datetime.now(timezone.utc).astimezone().date().isoformat()

    results = []
    for cat, url in FEEDS.items():
        feed = feedparser.parse(url)
        for e in feed.entries:
            if is_replacement(e):
                continue
            if not matched(e):
                continue

            results.append({
                "category": cat,
                "arxiv_id": extract_arxiv_id(e),
                "title": (e.get("title") or "").strip(),
                "authors": (e.get("dc_creator") or "").strip(),
                "link": (e.get("link") or "").strip(),
            })

    # 保存当天 JSON
    out_json = f"docs/data/{today}.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 生成首页 HTML（会自动包含历史 data/*.json）
    days = load_archive_index()
    html = render_html(today, results, days)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("docs/.nojekyll", "w", encoding="utf-8") as f:
        f.write("")

if __name__ == "__main__":
    main()
