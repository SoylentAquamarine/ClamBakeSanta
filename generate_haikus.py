import os
import datetime
from openai import OpenAI
from ftplib import FTP_TLS
from pathlib import Path

client = OpenAI()

# === File paths for GitHub Pages ===
BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
ARCHIVES_DIR = DOCS_DIR / "archives"
INDEX_HTML = DOCS_DIR / "index.html"
ARCHIVE_INDEX = ARCHIVES_DIR / "index.html"
RSS_FEED = DOCS_DIR / "feed.xml"

# === Load holiday data ===
def load_themes():
    month = datetime.datetime.now().strftime("%B").lower()
    day_code = datetime.datetime.now().strftime("%m-%d")
    themes = []

    for category in ["celebritybirthday", "randomholiday"]:
        file_path = BASE_DIR / f"{month}_{category}.txt"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith(day_code):
                        _, items = line.strip().split(":", 1)
                        themes.extend(item.strip() for item in items.split(","))
    return themes

# === Generate haiku with OpenAI ===
def generate_haiku(theme):
    prompt = f"Write a seasonal haiku in 5-7-5 form about: {theme}"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
        temperature=0.7
    )
    haiku = response.choices[0].message.content.strip()
    return f"{haiku}\nHappy #{format_hashtag(theme)} from @ClamBakeSanta"

def format_hashtag(theme):
    if theme.lower().startswith("birthday"):
        name = theme.replace("Birthday ", "").replace(" ", "")
        return f"HappyBirthday{name}"
    else:
        return theme.replace(" ", "").replace("'", "")

# === Save HTML ===
def format_html(date_str, haikus):
    header = f"<h1>Haikus for {date_str}</h1>\n"
    link = '<p><a href="archives/index.html">🗂 View Archive</a></p>\n'
    body = "\n".join(f"<p>{h.replace('\n', '<br>')}</p>" for h in haikus)
    return f"<html><body>{header}{link}{body}</body></html>"

def update_archive_index():
    links = []
    for file in sorted(ARCHIVES_DIR.glob("*.html"), reverse=True):
        if file.name != "index.html":
            date_str = file.stem
            links.append(f'<li><a href="{date_str}.html">{date_str}</a></li>')
    content = "<html><body><h1>Archive Index</h1><ul>" + "\n".join(links) + "</ul></body></html>"
    ARCHIVE_INDEX.write_text(content, encoding="utf-8")

# === Generate RSS Feed ===
def update_rss(haikus, date_str):
    items = ""
    for h in haikus:
        items += f"""
        <item>
            <title>Haiku for {date_str}</title>
            <description><![CDATA[{h.replace('\n', '<br>')}]]></description>
            <pubDate>{date_str}</pubDate>
            <guid>https://steve.lovestoblog.com/ClamBakeSanta/archives/{date_str}.html</guid>
            <link>https://steve.lovestoblog.com/ClamBakeSanta/archives/{date_str}.html</link>
        </item>
        """

    feed = f"""<?xml version="1.0"?>
    <rss version="2.0">
    <channel>
        <title>Clam Bake Santa</title>
        <link>https://steve.lovestoblog.com/ClamBakeSanta/</link>
        <description>Daily haikus from @ClamBakeSanta</description>
        {items}
    </channel>
    </rss>
    """
    RSS_FEED.write_text(feed, encoding="utf-8")

# === MAIN ===
def main():
    today = datetime.date.today().strftime("%Y-%m-%d")
    themes = load_themes()
    if not themes:
        print("No themes for today.")
        return

    DOCS_DIR.mkdir(exist_ok=True)
    ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)

    haikus = [generate_haiku(theme) for theme in themes]

    INDEX_HTML.write_text(format_html(today, haikus), encoding="utf-8")
    archive_file = ARCHIVES_DIR / f"{today}.html"
    archive_file.write_text(format_html(today, haikus), encoding="utf-8")
    update_archive_index()
    update_rss(haikus, today)

    print(f"✅ Generated {len(haikus)} haikus for {today}")

if __name__ == "__main__":
    main()
