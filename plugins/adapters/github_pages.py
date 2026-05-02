"""
github_pages — Adapter plugin.

Writes static HTML and RSS to docs/ so GitHub Pages can serve the site.

Produces / updates:
  docs/daily.html               — today's haikus (replaces index.html so the
                                  static project homepage can live at index.html)
  docs/archives/YYYY-MM-DD.html — permanent per-day archive page
  docs/archives/index.html      — auto-updated list of all archive links
  docs/feed.xml                 — RSS 2.0 feed (last 30 days)

GitHub Pages serves docs/ when enabled in repo settings.
Every git commit by the workflow = instant site update.
"""
from __future__ import annotations
import html as html_lib
import pathlib
from datetime import datetime
from zoneinfo import ZoneInfo

from framework.registry import register
from framework.adapters.base import BaseAdapter
from framework.models import Result


def _page(title: str, body: str, site_title: str, base_url: str) -> str:
    """Render a full HTML page with consistent nav and styling."""
    safe_title = html_lib.escape(title)
    safe_site = html_lib.escape(site_title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{
      --bg: #fdfaf5;
      --card: #ffffff;
      --accent: #2c6e49;
      --text: #1a1a2e;
      --muted: #666;
      --border: #e0d9cc;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: Georgia, 'Times New Roman', serif;
      max-width: 720px;
      margin: 0 auto;
      padding: 2rem 1.5rem;
      line-height: 1.7;
    }}
    header {{
      text-align: center;
      margin-bottom: 2rem;
      padding-bottom: 1rem;
      border-bottom: 2px solid var(--border);
    }}
    header h1 {{ font-size: 2rem; color: var(--accent); }}
    header p {{ color: var(--muted); font-style: italic; margin-top: 0.3rem; }}
    nav {{ margin: 1rem 0; text-align: center; }}
    nav a {{
      color: var(--accent);
      text-decoration: none;
      margin: 0 0.8rem;
      font-family: Arial, sans-serif;
      font-size: 0.9rem;
    }}
    nav a:hover {{ text-decoration: underline; }}
    .haiku-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1.5rem;
      margin: 1.5rem 0;
    }}
    .haiku-card h2 {{
      font-size: 1rem;
      color: var(--muted);
      font-family: Arial, sans-serif;
      margin-bottom: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .haiku-text {{
      font-size: 1.15rem;
      white-space: pre-line;
      line-height: 2;
    }}
    .hashtag {{ color: var(--accent); font-size: 0.9rem; margin-top: 0.5rem; font-family: Arial, sans-serif; }}
    .empty {{ text-align: center; color: var(--muted); padding: 3rem 0; font-style: italic; }}
    ul.archive-list {{ list-style: none; }}
    ul.archive-list li {{ padding: 0.4rem 0; border-bottom: 1px solid var(--border); }}
    ul.archive-list a {{ color: var(--accent); text-decoration: none; font-family: Arial, sans-serif; }}
    ul.archive-list a:hover {{ text-decoration: underline; }}
    footer {{
      margin-top: 3rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border);
      text-align: center;
      color: var(--muted);
      font-size: 0.85rem;
      font-family: Arial, sans-serif;
    }}
  </style>
</head>
<body>
  <header>
    <img src="{base_url}/santa_clambake.png" alt="Santa at a clam bake"
         style="width:180px;height:180px;object-fit:cover;border-radius:50%;margin-bottom:1rem;display:block;margin-left:auto;margin-right:auto;">
    <h1>{safe_site}</h1>
    <p>Daily haikus for today's holidays and birthdays</p>
  </header>
  <nav>
    <a href="{base_url}/">Home</a>
    <a href="{base_url}/daily.html">Today</a>
    <a href="{base_url}/archives/">Archive</a>
    <a href="{base_url}/feed.xml">RSS Feed</a>
  </nav>
  {body}
  <footer>
    © {datetime.now().year} Clam Bake Santa &nbsp;·&nbsp;
    Powered by GitHub Actions + GitHub Models &nbsp;·&nbsp;
    <a href="{base_url}/feed.xml" style="color:inherit">RSS</a>
  </footer>
</body>
</html>"""


def _render_haiku_cards(haiku_records: list[dict]) -> str:
    if not haiku_records:
        return '<p class="empty">🌊 The tide is quiet today. No holidays found.</p>'
    parts = []
    for rec in haiku_records:
        raw_theme = rec["theme"]
        # Prefix birthday themes with "Happy" so the card reads "HAPPY BIRTHDAY ..."
        display_theme = (
            f"Happy {raw_theme}" if raw_theme.lower().startswith("birthday") else raw_theme
        )
        theme = html_lib.escape(display_theme)
        lines = rec["haiku"].split("\n")
        # Last line is the hashtag line
        hashtag_line = html_lib.escape(lines[-1]) if lines else ""
        poem_lines = "\n".join(html_lib.escape(l) for l in lines[:-1])
        parts.append(
            f'<div class="haiku-card">'
            f'<h2>{theme}</h2>'
            f'<div class="haiku-text">{poem_lines}</div>'
            f'<div class="hashtag">{hashtag_line}</div>'
            f'</div>'
        )
    return "\n".join(parts)


@register("adapters", "github_pages")
class GitHubPagesAdapter(BaseAdapter):
    """
    Writes the static site files committed to docs/ by the workflow.
    No external services, no credentials needed — just file writes.
    """

    def publish(self, result: Result) -> bool:
        out_dir = pathlib.Path(self.config.get("output_dir", "docs"))
        archives_dir = out_dir / "archives"
        archives_dir.mkdir(parents=True, exist_ok=True)

        site_title = self.config.get("site_title", "Clam Bake Santa")
        base_url = self.config.get("site_base_url", "").rstrip("/")
        date_str = result.event.date_str
        haiku_records = result.metadata.get("haikus", [])

        # ── daily.html ────────────────────────────────────────────────────────
        cards = _render_haiku_cards(haiku_records)
        date_label = html_lib.escape(date_str)
        body = f"<p style='text-align:center;color:var(--muted);font-family:Arial,sans-serif;margin-bottom:1rem'>{date_label}</p>\n{cards}"
        (out_dir / "daily.html").write_text(
            _page(site_title, body, site_title, base_url),
            encoding="utf-8",
        )

        # ── archives/YYYY-MM-DD.html ──────────────────────────────────────────
        archive_body = (
            f"<h2 style='text-align:center;margin-bottom:1.5rem'>"
            f"Haikus for {html_lib.escape(date_str)}</h2>\n"
            + _render_haiku_cards(haiku_records)
        )
        (archives_dir / f"{date_str}.html").write_text(
            _page(f"{site_title} — {date_str}", archive_body, site_title, base_url),
            encoding="utf-8",
        )

        # ── archives/index.html ───────────────────────────────────────────────
        self._update_archive_index(archives_dir, site_title, base_url)

        # ── feed.xml ──────────────────────────────────────────────────────────
        self._write_rss(out_dir, archives_dir, site_title, base_url)

        return True

    def _update_archive_index(
        self, archives_dir: pathlib.Path, site_title: str, base_url: str
    ) -> None:
        files = sorted(
            [p for p in archives_dir.glob("*.html") if p.stem != "index"],
            key=lambda p: p.stem,
            reverse=True,
        )
        items = "".join(
            f'<li><a href="{html_lib.escape(p.name)}">{html_lib.escape(p.stem)}</a></li>'
            for p in files
        )
        body = (
            "<h2 style='margin-bottom:1rem'>All Haiku Archives</h2>"
            f"<ul class='archive-list'>{items}</ul>"
        )
        (archives_dir / "index.html").write_text(
            _page(f"{site_title} — Archives", body, site_title, base_url),
            encoding="utf-8",
        )

    def _write_rss(
        self,
        out_dir: pathlib.Path,
        archives_dir: pathlib.Path,
        site_title: str,
        base_url: str,
    ) -> None:
        files = sorted(
            [p for p in archives_dir.glob("*.html") if p.stem != "index"],
            key=lambda p: p.stem,
            reverse=True,
        )[:30]  # last 30 days in feed

        items_xml = []
        for p in files:
            ymd = p.stem
            link = f"{base_url}/archives/{p.name}"
            try:
                dt = datetime.strptime(ymd, "%Y-%m-%d")
                pub = dt.strftime("%a, %d %b %Y 12:00:00 +0000")
            except ValueError:
                pub = ""
            # Pull ALL haiku cards from the archive file for description
            try:
                import re
                raw_html = p.read_text(encoding="utf-8")
                # Extract each card: theme heading + poem lines + hashtag line
                cards = re.findall(
                    r'<div class="haiku-card">(.*?)</div>\s*</div>',
                    raw_html, re.S
                )
                card_blocks = []
                for card in cards:
                    theme_m = re.search(r'<h2[^>]*>(.*?)</h2>', card, re.S)
                    poem_m  = re.search(r'class="haiku-text">(.*?)</div>', card, re.S)
                    tag_m   = re.search(r'class="hashtag">(.*?)</div>', card, re.S)
                    theme_t = re.sub(r"<[^>]+>", "", theme_m.group(1)).strip() if theme_m else ""
                    poem_t  = re.sub(r"<[^>]+>", "", poem_m.group(1)).strip()  if poem_m  else ""
                    tag_t   = re.sub(r"<[^>]+>", "", tag_m.group(1)).strip()   if tag_m   else ""
                    # poem uses white-space:pre-line so newlines are literal \n
                    # strip trailing commas from each line before joining
                    poem_t = " / ".join(l.rstrip(",") for l in poem_t.split("\n"))
                    block = f"<p><strong>{theme_t}</strong><br>{poem_t}<br><em>{tag_t}</em></p>"
                    card_blocks.append(block)
                desc_html = "\n".join(card_blocks) if card_blocks else ""
            except Exception:
                desc_html = ""

            items_xml.append(
                f"  <item>\n"
                f"    <title>{html_lib.escape(f'{site_title} — {ymd}')}</title>\n"
                f"    <link>{html_lib.escape(link)}</link>\n"
                f"    <guid isPermaLink=\"true\">{html_lib.escape(link)}</guid>\n"
                f"    <pubDate>{pub}</pubDate>\n"
                f"    <description><![CDATA[{desc_html}]]></description>\n"
                f"  </item>"
            )

        rss = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0">\n'
            '  <channel>\n'
            f'    <title>{html_lib.escape(site_title)}</title>\n'
            f'    <link>{html_lib.escape(base_url)}/</link>\n'
            f'    <description>Daily haikus celebrating holidays and birthdays.</description>\n'
            f'    <language>en-us</language>\n'
            + "\n".join(items_xml) + "\n"
            '  </channel>\n'
            '</rss>\n'
        )
        (out_dir / "feed.xml").write_text(rss, encoding="utf-8")
