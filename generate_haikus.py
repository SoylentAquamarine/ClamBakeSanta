import os
import datetime
from openai import OpenAI
from ftplib import FTP_TLS
import ssl

client = OpenAI()

# === Configuration ===
ftp_host = os.getenv("FTP_HOST")
ftp_user = os.getenv("FTP_USER")
ftp_pass = os.getenv("FTP_PASS")
remote_dir = "/htdocs/ClamBakeSanta/"
base_url = "https://steve.lovestoblog.com/ClamBakeSanta/"

today = datetime.date.today()
today_str = today.strftime("%Y-%m-%d")
month = today.strftime("%B").lower()
mm_dd = today.strftime("%m-%d")

# === Load Holiday Data ===
def load_themes(filename):
    themes = []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(mm_dd):
                    parts = line.strip().split(":")
                    if len(parts) > 1:
                        items = parts[1].split(",")
                        themes.extend([item.strip() for item in items])
    except Exception as e:
        print(f"Error loading {filename}: {e}")
    return themes

celebs = load_themes(f"{month}_celebritybirthday.txt")
holidays = load_themes(f"{month}_randomholiday.txt")
themes = holidays + celebs

# === Generate Haikus ===
def generate_haiku(theme):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Write a haiku (5-7-5) about the given theme. Do not mention the theme name directly. Use vivid, sensory language."},
                {"role": "user", "content": f"{theme}"}
            ]
        )
        poem = response.choices[0].message.content.strip()
        if "birthday" in theme.lower():
            hashtag = "#HappyBirthday" + theme.replace("Birthday ", "").replace(" ", "")
        else:
            hashtag = "Happy #" + theme.replace(" ", "").replace("'", "")
        return f"{poem}\n\n{hashtag} from @ClamBakeSanta"
    except Exception as e:
        print(f"❌ Failed to generate haiku for {theme}: {e}")
        return None

haikus = [generate_haiku(theme) for theme in themes if generate_haiku(theme)]

# === HTML Generation ===
def format_html(date_str, haikus):
    header = f"<h1>Haikus for {date_str}</h1>\n"
    link = f'<p><a href="{base_url}archives/index.html">🗂 View Archive</a> | <a href="{base_url}feed.xml">📡 RSS Feed</a></p>\n'
    body = "\n".join(f"<p>{h.replace('\n', '<br>')}</p>" for h in haikus)
    return f"<html><body>{header}{link}{body}</body></html>"

index_html = format_html(today_str, haikus)
archive_path = f"archives/{today_str}.html"
archive_html = format_html(today_str, haikus)

# === Write Files Locally ===
with open("index.html", "w", encoding="utf-8") as f:
    f.write(index_html)

os.makedirs("archives", exist_ok=True)
with open(archive_path, "w", encoding="utf-8") as f:
    f.write(archive_html)

# === Update Archive Index ===
def update_archive_index():
    archive_files = [
        f for f in os.listdir("archives")
        if f.endswith(".html") and f != "index.html"
    ]
    archive_files.sort(reverse=True)
    links = [f'<li><a href="{filename}">{filename.replace(".html", "")}</a></li>' for filename in archive_files]

    html = f"""<html>
  <head><title>ClamBakeSanta Archives</title></head>
  <body>
    <h1>📚 Haiku Archive</h1>
    <p><a href="../index.html">⬅ Back to Today’s Haikus</a></p>
    <ul>
      {''.join(links)}
    </ul>
  </body>
</html>
"""
    with open("archives/index.html", "w", encoding="utf-8") as f:
        f.write(html)

update_archive_index()

# === Generate feed.xml ===
def generate_rss_feed(haikus, date_str):
    pub_date = today.strftime("%a, %d %b %Y 04:00:00 +0000")
    rss_items = ""
    for theme, haiku in zip(themes, haikus):
        title = theme
        desc = haiku.replace("\n", "<br>")
        rss_items += f"""
    <item>
      <title>{title}</title>
      <link>{base_url}archives/{date_str}.html</link>
      <pubDate>{pub_date}</pubDate>
      <description><![CDATA[
        {desc}
      ]]></description>
    </item>"""

    rss = f"""<?xml version=\"1.0\" encoding=\"UTF-8\" ?>
<rss version=\"2.0\">
  <channel>
    <title>ClamBakeSanta Daily Haikus</title>
    <link>{base_url}</link>
    <description>Daily haikus celebrating holidays and birthdays</description>
    <language>en-us</language>
    <lastBuildDate>{pub_date}</lastBuildDate>{rss_items}
  </channel>
</rss>
"""
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(rss)

generate_rss_feed(haikus, today_str)

# === Upload Files via FTP ===
def upload_file(ftp, local_path, remote_path):
    try:
        with open(local_path, "rb") as f:
            ftp.storbinary(f"STOR {remote_path}", f)
            print(f"✅ Uploaded {local_path} to {remote_path}")
    except Exception as e:
        print(f"❌ FTP upload failed for {local_path}: {e}")

try:
    context = ssl.create_default_context()
    context.set_ciphers("DEFAULT@SECLEVEL=1")
    ftps = FTP_TLS(context=context)
    ftps.connect(ftp_host, 21)
    ftps.login(ftp_user, ftp_pass)
    ftps.prot_p()
    ftps.cwd(remote_dir)

    upload_file(ftps, "index.html", "index.html")
    upload_file(ftps, "feed.xml", "feed.xml")

    ftps.cwd("archives")
    for filename in [f"{today_str}.html", "index.html"]:
        upload_file(ftps, f"archives/{filename}", filename)

    ftps.quit()
except Exception as e:
    print(f"❌ Unhandled FTP Exception: {e}")
