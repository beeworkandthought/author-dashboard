import feedparser
import urllib.parse
import re
import webbrowser
import os
from datetime import datetime
from collections import Counter

AUTHORS = [
    {"name": "한강", "queries": ["한강 작가", "Han Kang author"]},
    {"name": "박해영", "queries": ["박해영 작가", "박해영 극본"]},
    {"name": "무라카미 하루키", "queries": ["무라카미 하루키", "村上春樹"]},
    {"name": "다자이 오사무", "queries": ["다자이 오사무", "太宰治"]},
    {"name": "베르나르 베르베르", "queries": ["베르나르 베르베르", "Bernard Werber"]},
]

EVENT_KEYWORDS = ["사인회", "낭독회", "북토크", "시사회", "강연", "토크콘서트", "팬미팅", "출판기념", "이벤트", "행사", "공연"]

STOPWORDS = {
    "작가", "작품", "소설", "기자", "뉴스", "기사", "대한", "관련", "위한", "하는", "있는",
    "없는", "한다", "했다", "한다", "한국", "일본", "프랑스", "the", "and", "for", "with",
    "that", "this", "from", "are", "was", "his", "her", "에서", "으로", "에게", "까지",
    "부터", "이다", "있다", "없다", "하다", "되다", "않다", "것이", "수가", "들이",
}


def fetch_news(query, max_items=15):
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        title = entry.get("title", "")
        # Google News embeds source in title like "제목 - 출처"
        source = ""
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0].strip()
            source = parts[1].strip()
        items.append({
            "title": title,
            "link": entry.get("link", "#"),
            "published": entry.get("published", "")[:16],
            "source": source or entry.get("source", {}).get("title", ""),
        })
    return items


def get_author_data(author):
    all_news = []
    seen_titles = set()
    for query in author["queries"]:
        for item in fetch_news(query):
            if item["title"] not in seen_titles:
                seen_titles.add(item["title"])
                all_news.append(item)

    events = [n for n in all_news if any(kw in n["title"] for kw in EVENT_KEYWORDS)]
    general = [n for n in all_news if n not in events]

    # Keyword extraction from titles
    all_text = " ".join(n["title"] for n in all_news)
    words = re.findall(r'[가-힣]{2,}|[A-Za-z]{4,}', all_text)
    filtered = [w for w in words if w not in STOPWORDS and w not in author["name"]]
    counter = Counter(filtered)
    keywords = [w for w, _ in counter.most_common(10)]

    return {"news": general[:10], "events": events[:5], "keywords": keywords}


def build_html(authors_data):
    now = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")

    all_events = []
    for name, data in authors_data.items():
        for ev in data["events"]:
            all_events.append({"author": name, **ev})

    news_cards = ""
    for name, data in authors_data.items():
        keywords_html = "".join(
            f'<span class="keyword">{kw}</span>' for kw in data["keywords"]
        )
        news_rows = ""
        for n in data["news"]:
            news_rows += f"""
            <li>
                <a href="{n['link']}" target="_blank">{n['title']}</a>
                <span class="meta">{n['source']} &middot; {n['published']}</span>
            </li>"""

        if not data["news"]:
            news_rows = "<li class='empty'>최근 뉴스가 없습니다.</li>"

        news_cards += f"""
        <div class="card">
            <div class="card-header">
                <h2>{name}</h2>
            </div>
            <div class="keywords">{keywords_html}</div>
            <ul class="news-list">{news_rows}</ul>
        </div>"""

    events_rows = ""
    for ev in all_events:
        events_rows += f"""
        <li>
            <span class="event-author">{ev['author']}</span>
            <a href="{ev['link']}" target="_blank">{ev['title']}</a>
            <span class="meta">{ev['source']} &middot; {ev['published']}</span>
        </li>"""

    if not all_events:
        events_rows = "<li class='empty'>현재 등록된 이벤트 소식이 없습니다.</li>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>작가 대시보드</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #f4f4f0;
    color: #1a1a1a;
    min-height: 100vh;
  }}
  header {{
    background: #1a1a1a;
    color: #fff;
    padding: 24px 40px;
    display: flex;
    align-items: baseline;
    gap: 16px;
  }}
  header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }}
  header .updated {{ font-size: 13px; color: #888; margin-left: auto; }}

  .tabs {{
    display: flex;
    gap: 0;
    background: #fff;
    border-bottom: 2px solid #e0e0e0;
    padding: 0 40px;
  }}
  .tab {{
    padding: 14px 24px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    color: #888;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: color 0.2s;
  }}
  .tab.active {{ color: #1a1a1a; border-bottom-color: #1a1a1a; }}

  .tab-content {{ display: none; padding: 32px 40px; }}
  .tab-content.active {{ display: block; }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 24px;
  }}

  .card {{
    background: #fff;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  }}
  .card-header {{ margin-bottom: 14px; }}
  .card-header h2 {{ font-size: 17px; font-weight: 700; }}

  .keywords {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 18px; }}
  .keyword {{
    background: #f0f0eb;
    color: #444;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 20px;
    font-weight: 500;
  }}

  .news-list {{ list-style: none; }}
  .news-list li {{
    padding: 10px 0;
    border-bottom: 1px solid #f0f0f0;
    line-height: 1.4;
  }}
  .news-list li:last-child {{ border-bottom: none; }}
  .news-list a {{
    color: #1a1a1a;
    text-decoration: none;
    font-size: 14px;
    display: block;
    margin-bottom: 3px;
  }}
  .news-list a:hover {{ color: #555; text-decoration: underline; }}
  .meta {{ font-size: 11px; color: #aaa; }}
  .empty {{ color: #bbb; font-size: 13px; }}

  .events-section {{
    background: #fff;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
    max-width: 860px;
  }}
  .events-section h2 {{ font-size: 17px; font-weight: 700; margin-bottom: 18px; }}
  .events-list {{ list-style: none; }}
  .events-list li {{
    padding: 12px 0;
    border-bottom: 1px solid #f0f0f0;
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 12px;
    align-items: start;
  }}
  .events-list li:last-child {{ border-bottom: none; }}
  .event-author {{
    font-size: 12px;
    font-weight: 700;
    color: #fff;
    background: #1a1a1a;
    padding: 3px 8px;
    border-radius: 4px;
    white-space: nowrap;
    text-align: center;
    align-self: center;
  }}
  .events-list a {{
    color: #1a1a1a;
    text-decoration: none;
    font-size: 14px;
    display: block;
    margin-bottom: 3px;
  }}
  .events-list a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<header>
  <h1>작가 대시보드</h1>
  <span class="updated">마지막 업데이트: {now}</span>
</header>

<div class="tabs">
  <div class="tab active" onclick="switchTab('news', this)">뉴스 피드</div>
  <div class="tab" onclick="switchTab('events', this)">이벤트</div>
</div>

<div id="tab-news" class="tab-content active">
  <div class="grid">
    {news_cards}
  </div>
</div>

<div id="tab-events" class="tab-content">
  <div class="events-section">
    <h2>사인회 · 낭독회 · 북토크 · 시사회</h2>
    <ul class="events-list">
      {events_rows}
    </ul>
  </div>
</div>

<script>
function switchTab(name, el) {{
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  el.classList.add('active');
}}
</script>
</body>
</html>"""


def main():
    print("뉴스를 가져오는 중...")
    authors_data = {}
    for author in AUTHORS:
        print(f"  - {author['name']} 검색 중...")
        authors_data[author["name"]] = get_author_data(author)

    output_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(build_html(authors_data))

    print(f"\n완료! 대시보드를 브라우저로 엽니다...")
    webbrowser.open(f"file://{output_path}")


if __name__ == "__main__":
    main()
