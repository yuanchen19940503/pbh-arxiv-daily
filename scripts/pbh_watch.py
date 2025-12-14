import json
import os
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

LIST_PAGES = {
    "astro-ph.CO": "https://arxiv.org/list/astro-ph.CO/new",
    "gr-qc": "https://arxiv.org/list/gr-qc/new",
}

PATTERNS = [
    r"primordial\s+black\s+holes?",
    r"\bPBHs?\b",
]
REGEX = re.compile("|".join(PATTERNS), re.IGNORECASE)

HEADERS = {
    "User-Agent": "pbh-arxiv-daily (GitHub Actions); contact: your-email@example.com"
}

def ensure_dirs():
    os.makedirs("docs/data", exist_ok=True)

def clean_label(s: str, label: str) -> str:
    s = (s or "").strip()
    if s.lower().startswith(label.lower()):
        return s[len(label):].strip()
    return s

def parse_listing_date(soup: BeautifulSoup) -> str:
    # e.g. "Showing new listings for Friday, 12 December 2025"
    h3 = soup.find("h3", string=re.compile(r"Showing new listings for", re.I))
    if not h3:
        raise RuntimeError("Cannot find listing date header on /new page.")
    text = h3.get_text(" ", strip=True)
    m = re.search(r"Showing new listings for\s+(.*)$", text, re.I)
    if not m:
        raise RuntimeError(f"Cannot parse listing date from header: {text}")
    date_str = m.group(1).strip()  # "Friday, 12 December 2025"
    dt = datetime.strptime(date_str, "%A, %d %B %Y")
    return dt.date().isoformat()

def parse_all_entries(soup: BeautifulSoup):
    out = []
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt", recursive=False)
        dds = dl.find_all("dd", recursive=False)
        for dt, dd in zip(dts, dds):
            dt_text = dt.get_text(" ", strip=True)

            # 排除 replacements（在 /new 页面里会标成 "(replaced)"）
            if "(replaced)" in dt_text:
                continue

            abs_a = dt.find("a", href=re.compile(r"^/abs/"))
            if not abs_a or not abs_a.get("href"):
                continue

            link = "https://arxiv.org" + abs_a["href"].strip()
            arxiv_id = abs_a.get_text(strip=True).replace("arXiv:", "").strip()

            title_div = dd.find("div", class_=re.compile(r"list-title"))
            title = clean_label(title_div.get_text(" ", strip=True) if title_div else "", "Title:")

            auth_div = dd.find("div", class_=re.compile(r"list-authors"))
            authors = [a.get_text(" ", strip=True) for a in auth_div.find_all("a")] if auth_div else []

            fulltext = dd.get_text(" ", strip=True)

            out.append({
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": authors,
                "link": link,
                "fulltext": fulltext,
            })
    return out


def find_h3_startswith(soup: BeautifulSoup, prefix: str):
    for h3 in soup.find_all("h3"):
        txt = h3.get_text(" ", strip=True)
        if txt.startswith(prefix):
            return h3
    return None

def parse_section_entries(soup: BeautifulSoup, section_title_prefix: str):
    h3 = find_h3_startswith(soup, section_title_prefix)
    if not h3:
        return []
    dl = h3.find_next("dl")
    if not dl:
        return []

    dts = dl.find_all("dt")
    dds = dl.find_all("dd")
    out = []

    for dt, dd in zip(dts, dds):
        # abs 链接：优先 title=Abstract，找不到就用 href=/abs/
        abs_a = dt.find("a", title=re.compile("Abstract", re.I))
        if not abs_a:
            abs_a = dt.find("a", href=re.compile(r"^/abs/"))
        if not abs_a or not abs_a.get("href"):
            continue

        link = "https://arxiv.org" + abs_a["href"].strip()
        arxiv_id = abs_a.get_text(strip=True).replace("arXiv:", "").strip()

        title_div = dd.find("div", class_=re.compile(r"list-title"))
        title = clean_label(title_div.get_text(" ", strip=True) if title_div else "", "Title:")

        auth_div = dd.find("div", class_=re.compile(r"list-authors"))
        authors = [a.get_text(" ", strip=True) for a in auth_div.find_all("a")] if auth_div else []

        # 关键修改：把 dd 里的全文拿出来（包含摘要那段文本）
        fulltext = dd.get_text(" ", strip=True)

        out.append({
            "category": section_title_prefix,
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "link": link,
            "fulltext": fulltext,  # 新增字段：用于匹配
        })

    return out


def is_match(item) -> bool:
    return bool(REGEX.search(item.get("fulltext", "")))




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
    total = 0
    author_count = {}
    for d in days:
        items = load_json(f"docs/data/{d}.json") or []
        total += len(items)
        for it in items:
            for a in it.get("authors", []):
                author_count[a] = author_count.get(a, 0) + 1
    top_authors = sorted(author_count.items(), key=lambda x: (-x[1], x[0]))[:30]
    return {"update_days": len(days), "total_papers": total, "top_authors": top_authors}

def render_html(latest_day, items, stats, days_desc):
    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<","&lt;").replace(">","&gt;")

    if not items:
        items_html = "<p>该批次无匹配条目。</p>"
    else:
        blocks = []
        for it in items:
            authors = ", ".join(it.get("authors", []))
            blocks.append(
                "<div class='item'>"
                f"<div><b>{esc(it.get('arxiv_id',''))}</b></div>"
                f"<div class='title'><a href='{esc(it.get('link',''))}' target='_blank' rel='noopener'>{esc(it.get('title',''))}</a></div>"
                f"<div class='authors authors-hidden'>{esc(authors)}</div>"
                "</div>"
            )
        items_html = "\n".join(blocks)

    archive_links = ""
    for d in days_desc[:30]:
        archive_links += f"<li><a href='data/{d}.json' target='_blank' rel='noopener'>{d}.json</a></li>"

    top_auth = ""
    for name, cnt in stats["top_authors"]:
        top_auth += f"<li>{esc(name)} — {cnt}</li>"

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
    .title {{ margin: 6px 0; }}
    .authors-hidden {{ display: none; }}
    button {{ padding: 6px 10px; border: 1px solid #ccc; background: #fff; border-radius: 8px; cursor: pointer; }}
    code {{ background: #f6f8fa; padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>PBH arXiv Daily ({latest_day})</h1>
  <div class="meta">
    来源：<code>astro-ph.CO/new</code> 与 <code>gr-qc/new</code>；规则：匹配关键词（PBH / primordial black hole），仅统计 New submissions + Cross-lists，不包含 Replacements。<br/>
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
      <ol>{top_auth}</ol>
    </div>
  </div>

<script>
  document.getElementById("toggleAuthors").addEventListener("click", () => {{
    document.querySelectorAll(".authors").forEach(el => el.classList.toggle("authors-hidden"));
  }});
</script>
</body>
</html>
"""

def main():
    ensure_dirs()

    # 抓两个页面，并以“最新批次日期”为准（一般两者相同）
    parsed = {}
    dates = []

    for name, url in LIST_PAGES.items():
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        day = parse_listing_date(soup)
        dates.append(day)

        items = parse_all_entries(soup)


        # 写入时保留来源分类名（astro-ph.CO/gr-qc），便于统计
        for it in items:
            it["source"] = name

        parsed[name] = (day, items)

    latest_day = max(dates)

    # 合并两个页面中“属于同一批次日期”的条目
    merged = []
    for name, (day, items) in parsed.items():
        if day != latest_day:
            continue
        for it in items:
            if is_match(it):
                merged.append({
                    "source": it["source"],          # astro-ph.CO or gr-qc
                    "arxiv_id": it["arxiv_id"],
                    "title": it["title"],
                    "authors": it["authors"],
                    "link": it["link"],
                })

    day_path = f"docs/data/{latest_day}.json"
    existing = load_json(day_path)
    if existing == merged:
        print(f"No new arXiv listings batch (listing date: {latest_day}). Nothing to update.")
        return

    write_json(day_path, merged)

    days = list_day_files()
    days_desc = sorted(days, reverse=True)
    stats = compute_stats(days)

    html = render_html(latest_day, merged, stats, days_desc)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    with open("docs/.nojekyll", "w", encoding="utf-8") as f:
        f.write("")

if __name__ == "__main__":
    main()
