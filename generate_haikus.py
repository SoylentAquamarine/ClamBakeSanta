import os
from datetime import datetime
from pathlib import Path
from ftplib import FTP
from openai import OpenAI

# Load API and FTP credentials from environment
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")

# Get today's date info
now = datetime.now()
month = now.strftime("%B").lower()
day_key = now.strftime("%m-%d")
full_date = now.strftime("%Y-%m-%d")

def load_themes(month, day_key):
    themes = []
    for category in ["celebritybirthday", "randomholiday"]:
        file_path = f"{month}_{category}.txt"
        print(f"Looking for file: {file_path}")
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            continue
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                print(f"Checking line: {line.strip()}")
                if line.strip().startswith(f"{day_key}:"):
                    print(f"✅ Matched line: {line.strip()}")
                    themes.extend(x.strip() for x in line.split(":", 1)[1].split(","))
    print("🎯 Final themes:", themes)
    return themes

def generate_haiku(prompt):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{
            "role": "user",
            "content": f"Write a 3-line haiku about {prompt}, sensory and seasonal if possible. Do not use the theme name in the haiku."
        }]
    )
    return response.choices[0].message.content.strip()

def format_html(date_str, haikus):
    header = f"<h1>Haikus for {date_str}</h1>\n"
    body = "\n".join(f"<p>{h.replace('\n', '<br>')}</p>" for h in haikus)
    return f"<html><body>{header}{body}</body></html>"

def save_html(content, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def upload_via_ftp(file_path, remote_path):
    try:
        if not os.path.exists(file_path):
            print(f"❌ File does not exist: {file_path}")
            return

        with FTP(FTP_HOST) as ftp:
            print("🔌 Connecting to FTP...")
            ftp.login(FTP_USER, FTP_PASS)
            print("✅ FTP login successful.")
            print("📂 Current FTP working directory:", ftp.pwd())
            print("📄 FTP directory contents:")
            ftp.retrlines('LIST')

            try:
                ftp.mkd('htdocs/ClamBakeSanta/archives')
                print("📁 Created 'archives' directory.")
            except Exception as e:
                print("ℹ️ 'archives' may already exist:", e)

            print(f"⬆️ Uploading {file_path} to {remote_path}")
            with open(file_path, 'rb') as f:
                ftp.storbinary(f'STOR {remote_path}', f)
            print("✅ Upload complete.")
    except Exception as e:
        print("❌ FTP upload failed:", e)
        raise

def main():
    themes = load_themes(month, day_key)

    if not themes:
        print("No themes for today.")
        return

    haikus = []
    for theme in themes:
        print(f"Generating haiku for: {theme}")
        haiku = generate_haiku(theme)
        hashtag = f"Happy #{theme.replace(' ', '')}" if not theme.startswith("Birthday") else f"#Happy{theme.replace(' ', '')}"
        haikus.append(f"{haiku}\n<br>{hashtag} from @ClamBakeSanta")

    Path("archives").mkdir(exist_ok=True)

    archive_file = f"archives/{full_date}.html"
    archive_html = format_html(full_date, haikus)
    save_html(archive_html, archive_file)

    index_html = format_html("Today", haikus)
    save_html(index_html, "index.html")

    archive_links = []
    for file in sorted(Path("archives").glob("*.html")):
        name = file.stem
        archive_links.append(f'<li><a href="{file.name}">{name}</a></li>')
    archive_index = f"<html><body><h1>Archives</h1><ul>{''.join(archive_links)}</ul></body></html>"
    save_html(archive_index, "archives/index.html")

    print("📁 Local files before upload:", os.listdir('.'))
    print("📁 Archives directory:", os.listdir('archives'))

    upload_via_ftp("index.html", "htdocs/ClamBakeSanta/index.html")
    upload_via_ftp(archive_file, f"htdocs/ClamBakeSanta/archives/{full_date}.html")
    upload_via_ftp("archives/index.html", "htdocs/ClamBakeSanta/archives/index.html")

    print("✅ Website content generated and uploaded.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ Unhandled Exception:", e)
        import traceback
        traceback.print_exc()
        exit(1)
