import os
import datetime
import openai

# Setup OpenAI
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Dates
today = datetime.date.today()
month_str = today.strftime("%B").lower()
date_str = today.strftime("%Y-%m-%d")
md_str = today.strftime("%m-%d")

# Paths
docs_dir = "docs"
archive_dir = os.path.join(docs_dir, "archives")
index_path = os.path.join(docs_dir, "index.html")
archive_path = os.path.join(archive_dir, f"{date_str}.html")
rss_path = os.path.join(docs_dir, "feed.xml")
archive_index_path = os.path.join(archive_dir, "index.html")

# Ensure folders exist
os.makedirs(docs_dir, exist_ok=True)
os.makedirs(archive_dir, exist_ok=True)

def load_themes():
    themes = []
    for fname in [f"{month_str}_celebritybirthday.txt", f"{month_str}_randomholiday.txt"]:
        if not os.path.exists(fname):
            continue
        with open(fname, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(md_str):
                    _, data = line.strip().split(":", 1)
                    themes.extend([item.strip() for item in data.split(",")])
    return themes

def generate_haiku(theme):
    prompt = f"Write a seasonal haiku about {theme} in 5-7-5 format."
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.7,
        )
        haiku = response.choices[0].message.content.strip()
        tag = f"#Happy{theme.replace(' ', '')}" if theme.lower().startswith("birthday") else f"#Happy{theme.replace(' ', '')}"
        return f"{haiku}\nHappy {tag} from @ClamBakeSanta"
    except Exception as e:
        return f"(Error: {e})"

def format_html(date_str, haikus):
    header = f"<h1>Haikus for {date_str}</h1>\n"
    link = '<p><a href="archives/index.html">🗂 View Archive</a></p>\n'
    body = "\n".join(f"<p>{h.replace('\n', '<br>')}</p>" for h in haikus)
    return f"<html><body>{header}{link}{body}</body></html>"

def format_rss(haikus, date_str):
    items = ""
    for h in haikus:
        items += f"""
  <item>
    <title>Haiku for {date_str}</title>
    <description><![CDATA[{h}]]></description>
    <pubDate>{today.strftime("%a, %d %b %Y 00:00:00 GMT")}</pubDate>
    <guid>https://{os.getenv('GITHUB_PAGES_DOMAIN')}/ClamBakeSanta/archives/{date_str}.html</guid>
    <link>https://{os.getenv('GITHUB_PAGES_DOMAIN')}/ClamBakeSanta/archives/{date_str}.html</link>
  </item>"""
    return f"""<?xml version="1.0"?>
<rss version="2.0">
<channel>
  <title>ClamBakeSanta Daily Haikus</title>
  <link>https://{os.getenv('GITHUB_PAGES_DOMAIN')}/ClamBakeSanta/</link>
  <description>Daily haikus for holidays and celebrity birthdays</description>
  <language>en-us</language>{items}
</channel>
</rss>"""

def update_archive_index():
    files = sorted(
        [f for f in os.listdir(archive_dir) if f.endswith(".html") and f != "index.html"],
        reverse=True
    )
    links = "\n".join(
        f'<li><a href="{f}">{f.replace(".html", "")}</a></li>' for f in files
    )
    content = f"<html><body><h1>Haiku Archive</h1><ul>{links}</ul></body></html>"
    with open(archive_index_path, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    themes = load_themes()
    if not themes:
        print("No holidays for today.")
        return

    haikus = [generate_haiku(t) for t in themes]

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(format_html(date_str, haikus))

    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(format_html(date_str, haikus))

    with open(rss_path, "w", encoding="utf-8") as f:
        f.write(format_rss(haikus, date_str))

    update_archive_index()
    print("✅ All haiku files generated.")

if __name__ == "__main__":
    main()
