import os
from datetime import datetime
from pathlib import Path
from ftplib import FTP

from days import themes  # your existing MM-DD dictionary
import openai

# Load env variables
openai.api_key = os.getenv("OPENAI_API_KEY")
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")

def generate_haiku(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": f"Write a 3-line haiku about {prompt}, sensory, seasonal if possible. Do not use the name of the theme in the haiku."}]
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
    with FTP(FTP_HOST) as ftp:
        ftp.login(FTP_USER, FTP_PASS)
        with open(file_path, 'rb') as f:
            ftp.storbinary(f'STOR {remote_path}', f)

def main():
    today = datetime.now().strftime("%m-%d")
    full_date = datetime.now().strftime("%Y-%m-%d")
    date_themes = themes.get(today, [])

    if not date_themes:
        print("No themes for today.")
        return

    haikus = []
    for theme in date_themes:
        haiku = generate_haiku(theme)
        haikus.append(f"{haiku}\n<br>Happy #{theme.replace(' ', '')} from @ClamBakeSanta")

    # Create archive folder if needed
    Path("archives").mkdir(exist_ok=True)

    # Save today's file
    archive_file = f"archives/{full_date}.html"
    archive_html = format_html(full_date, haikus)
    save_html(archive_html, archive_file)

    # Update index.html
    index_html = format_html("Today", haikus)
    save_html("index.html", index_html)

    # Rebuild archives/index.html
    archive_links = []
    for file in sorted(Path("archives").glob("*.html")):
        name = file.stem
        archive_links.append(f'<li><a href="{file.name}">{name}</a></li>')
    archive_index = f"<html><body><h1>Archives</h1><ul>{''.join(archive_links)}</ul></body></html>"
    save_html("archives/index.html", archive_index)

    # FTP Upload
    upload_via_ftp("index.html", "index.html")
    upload_via_ftp(archive_file, f"archives/{full_date}.html")
    upload_via_ftp("archives/index.html", "archives/index.html")
    print("Website content generated and uploaded.")

if __name__ == "__main__":
    main()
