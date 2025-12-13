import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

FEEDS = {
    "astro-ph.CO": "https://rss.arxiv.org/rss/astro-ph.CO",
    "gr-qc": "https://rss.arxiv.org/rss/gr-qc",
}

# 关键词：primordial black hole(s) / PBH(s) 
PATTERNS = [
    r"primordial\s+black\s+holes?",
    r"\bPBHs?\b",
]
REGEX = re.compile("|".join(PATTERNS), re.IGNORECASE)


def ensure_dirs():
    os.makedirs("docs/data", exist_ok=True)


def parse_listing_date(feed) -> str:
    """
    返回本次 new listings 的日期（YYYY-MM-DD）。
    优先从 feed 标题里解析 “… for Fri, 12 Dec 2025”；
    其次用 feed 的 updated/published。
    """
    title = (feed.feed.get("title") or "").strip()
    m = re.search(r"\bfor\s+(.+)$", title)
    if m:
        date_str = m.group(1).strip()
        # 常见格式：Fri, 12 Dec 2025
        for fmt in ("%a, %d %b %Y", "%d %b %Y"):
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.date().isoformat()
            except ValueError:
                pass

    updated = (feed.feed.get("updated") or feed.feed.get("published") or "").strip()
    if updated:
        try:
            dt = parsedate_to_datetime(updated)
            return dt.astimezone(timezone.utc).date().isoformat()
        except Exception:
            pass

    # 实在解析不到就退回到“今天”（不推荐，但保证不崩）
    return datetime.now(timezone.utc).date().isoformat()


def entry_text(entry) -> str:
    # feedparser 对 RSS/Atom 映射不完全一致：摘要可能在 summary 或 description 或 content
    parts = []
    parts.append(entry.get("title") or "")
    parts.append(entry.get("summary") or "")
    parts.append(entry.get("description") or "")

    if entry.get("content"):
        parts.append(" ".join([c.get("value", "") for c in entry.get("content", [])]))

    # 作者：优先 authors[].name，其次 dc_creator
    if entry.get("authors"):
        parts.append(" ".join([a.get("name", "") for a in entry.get("authors", [])]))
    parts.append(entry.get("dc_creator") or "")

    return " ".join(parts)


def get_authors(entry):
    if entry.get("authors"):
        return [a.get("name", "").strip() for a in entry.get("authors", []) if a.get("name")]
    dc = (entry.get("dc_creator") or "").strip()
    return [dc] if dc else []


def is_replacement(entry) -> bool:
    at = (entry.get("arxiv_announce_type") or "").lower()
    if "replace" in at:
        return True

    # 兜底：有时 replacement 信息只在摘要文本里
    txt = (entry.get("summary") or entry.get("description") or "").lower()
    return "announce type: replace" in txt


def extract_arxiv_id(entry) -> str:
    txt = entry.get("summary") or entry.get("description") or ""
    m = re.search(r"arXiv:(\d{4}\.\d{4,5})(v\d+)?", txt)
    if m:
        return m.group(1)

    link = entry.get("link") or ""
    m = re.search(r"/abs/(\d{4}\.\d{4,5})", link)
    return m.group(1) if m else ""


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def list_day_files():
    days = []
    if os.path.isdir("docs/data"):
        for fn in os.listdir("docs/data"):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", fn):
                days.append(fn.replace(".json", ""))
    return sorted(days)


def compute_stats(days):
    total_papers = 0
    author_count = {}

    for d in days:
        items = load_json(f"docs/data/{d}.json") or []
        total_papers += len(items)
        for it in items:
            for a in it.get("authors", []):
                author_count[a] = author_count.get(a, 0) + 1

    top_authors = sorted(author_count.items(), key=lambda x: (-x[1], x[0]))[:30]
    return {
        "update_days": len(days),
        "total_papers": total_papers,
        "top_authors": top_authors,
    }


def render_html(latest_day, latest_items, stats, days_desc):
    def esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 列表
    if not latest_items:
        items_html = "<p>该批次无匹配条目。</p>"
    else:
        rows = []
        for it in latest_items:
            authors = ", ".join(it.get("authors", []))
            rows.append(
                "<div class='item'>"
                f"<div class='id'><b>{esc(it.get('arxiv_id',''))}</b> <span class='cat'>{esc(it.get('category',''))}</span></div>"
                f"<div class='title'><a href='{esc(it.get('link',''))}' target='_blank' rel='noopener'>{esc(it.get('title',''))}</a></div>"
                f"<div class='authors authors-hidden'>{esc(authors)}</div>"
                "</div>"
            )
        items_html = "\n".join(rows)

    # 归档链接（最近 30 次更新）
    archive_links = ""
    for d in days_desc[:30]:
        archive_links += f"<li><a href='data/{d}.json' target='_blank' rel='noopener'>{d}.json</a></li>"

    top_authors_html = ""
    for name, cnt in stats["top_authors"]:
        top_authors_html += f"<li>{esc(name)} — {cnt}</li>"

    return f"""<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PBH arXiv Daily - {latest_day}</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial; margin: 24px; line-height: 1.5; }}
    .meta {{ color: #555; margin-bottom: 16px; }}
    .cols {{ display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }}
    @media (max-width: 900px) {{ .cols {{ grid-template-columns: 1fr; }} }}
    .item {{ padding: 12px 0; border-bottom: 1px solid #eee; }}
    .id {{ font-size: 14px; }}
    .cat {{ color: #666; margin-left: 8px; }}
    .title {{ font-size: 16px; margin: 6px 0; }}
    .authors {{ font-size: 13px; color: #333; }}
    .authors-hidden {{ display: none; }}
    button {{ padding: 6px 10px; border: 1px solid #ccc; background: #fff; border-radius: 8px; cursor: pointer; }}
    code {{ background: #f6f8fa; padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>PBH arXiv Daily ({latest_day})</h1>
  <div class="meta">
    来源：<code>astro-ph.CO</code> 与 <code>gr-qc</code> 的 arXiv RSS；规则：匹配关键词（PBH / primordial black hole 等），排除 <code>announce_type</code> 含 <code>replace</code> 的条目。<br/>
    已记录 <b>{stats["update_days"]}</b> 次 arXiv 更新批次；累计匹配 <b>{stats["total_papers"]}</b> 篇。
  </div>

  <div style="margin: 10px 0 18px 0;">
    <button id="toggleAuthors">显示/隐藏作者</button>
  </div>

  <div class="cols">
    <div>
      <h2>本批次匹配</h2>
      {items_html}
    </div>
    <div>
      <h2>归档（最近30次更新 JSON）</h2>
      <ul>{archive_links}</ul>

      <h2 style="margin-top:18px;">Top 作者（累计匹配次数）</h2>
      <ol>{top_authors_html}</ol>
    </div>
  </div>

<script>
  document.getElementById("toggleAuthors").addEventListener("click", () => {{
    document.querySelectorAll(".authors").forEach(el => {{
      el.classList.toggle("authors-hidden");
    }});
  }});
</script>
</body>
</html>
"""


def main():
    ensure_dirs()

    # 读取两条 feed，并解析各自的“批次日期”
    parsed = {}
    dates = []
    for cat, url in FEEDS.items():
        f = feedparser.parse(url)
        d = parse_listing_date(f)
        parsed[cat] = (f, d)
        dates.append(d)

    # 最新批次日期（通常两者相同）
    latest_day = max(dates)

    # 只处理“最新批次”的 feed（避免出现一个更新、一个没更新时混在一起）
    latest_items = []
    for cat, (f, d) in parsed.items():
        if d != latest_day:
            continue
        for e in f.entries:
            if is_replacement(e):
                continue
            if not REGEX.search(entry_text(e)):
                continue
            latest_items.append({
                "category": cat,
                "arxiv_id": extract_arxiv_id(e),
                "title": (e.get("title") or "").strip(),
                "authors": get_authors(e),
                "link": (e.get("link") or "").strip(),
            })

    day_path = f"docs/data/{latest_day}.json"
    existing = load_json(day_path)
    # 如果同一天已存在且结果完全一致，则不写入、不更新页面（等同于“今天没有新批次更新”）
    if existing == latest_items:
        print(f"No new arXiv batch (latest listing date: {latest_day}). Nothing to update.")
        return

    write_json(day_path, latest_items)

    # 更新统计 + 首页
    days = list_day_files()
    days_desc = sorted(days, reverse=True)
    stats = compute_stats(days)

    html = render_html(latest_day, latest_items, stats, days_desc)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    with open("docs/.nojekyll", "w", encoding="utf-8") as f:
        f.write("")


if __name__ == "__main__":
    main()
