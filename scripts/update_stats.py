#!/usr/bin/env python3
"""
Fetches live GitHub stats for the account and regenerates assets/stats.svg
plus the "last synced" line in README.md. Run daily by
.github/workflows/daily-sync.yml.
"""
import os
import sys
import json
import urllib.request
from datetime import datetime, timezone

USERNAME = "Krishsudharsun"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API_ROOT = "https://api.github.com"


def api_get(path):
    req = urllib.request.Request(f"{API_ROOT}{path}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{USERNAME}-profile-sync")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def fetch_stats():
    user = api_get(f"/users/{USERNAME}")
    repos = api_get(f"/users/{USERNAME}/repos?per_page=100")

    lang_counts = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    top_langs = sorted(lang_counts.items(), key=lambda x: -x[1])[:4]
    total = sum(c for _, c in top_langs) or 1

    created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))

    return {
        "public_repos": user["public_repos"],
        "followers": user["followers"],
        "following": user["following"],
        "member_since": created.strftime("%b %Y"),
        "top_langs": top_langs,
        "total_lang_repos": total,
    }


LANG_COLORS = {
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "HTML": "#e34f26",
    "CSS": "#563d7c",
    "Python": "#39d353",
}
DEFAULT_COLOR = "#8b949e"


def render_svg(stats, synced_at):
    bar_x = 620
    bar_w = 220
    rows = []
    y = 96
    for lang, count in stats["top_langs"]:
        width = int(bar_w * count / stats["total_lang_repos"])
        color = LANG_COLORS.get(lang, DEFAULT_COLOR)
        rows.append(f'''
    <text x="480" y="{y}" fill="#e6edf3">{lang}</text>
    <rect x="{bar_x}" y="{y - 10}" width="{bar_w}" height="12" fill="#161b22"/>
    <rect x="{bar_x}" y="{y - 10}" width="{max(width, 8)}" height="12" fill="{color}"/>''')
        y += 32

    lang_block = "".join(rows) if rows else '<text x="480" y="96" fill="#484f58">no language data yet</text>'

    svg = f'''<svg width="900" height="300" viewBox="0 0 900 300" xmlns="http://www.w3.org/2000/svg" font-family="'Courier New', monospace">
  <rect width="900" height="300" rx="8" fill="#0d1117"/>
  <rect width="900" height="300" rx="8" fill="none" stroke="#30363d" stroke-width="1.5"/>

  <rect width="900" height="30" rx="8" fill="#161b22"/>
  <rect y="18" width="900" height="12" fill="#161b22"/>
  <circle cx="20" cy="15" r="5" fill="#ff5f56"/>
  <circle cx="38" cy="15" r="5" fill="#ffbd2e"/>
  <circle cx="56" cy="15" r="5" fill="#27c93f"/>
  <text x="450" y="20" text-anchor="middle" font-size="11" fill="#8b949e">stat --account={USERNAME.lower()} --live</text>

  <g font-size="13">
    <text x="30" y="64" fill="#8b949e">account age</text>
    <text x="230" y="64" fill="#e6edf3" font-weight="700">since {stats["member_since"]}</text>

    <text x="30" y="94" fill="#8b949e">public repos</text>
    <text x="230" y="94" fill="#39d353" font-weight="700">{stats["public_repos"]}</text>

    <text x="30" y="124" fill="#8b949e">followers</text>
    <text x="230" y="124" fill="#58a6ff" font-weight="700">{stats["followers"]}</text>

    <text x="30" y="154" fill="#8b949e">following</text>
    <text x="230" y="154" fill="#58a6ff" font-weight="700">{stats["following"]}</text>

    <text x="30" y="184" fill="#8b949e">org</text>
    <text x="230" y="184" fill="#e6edf3" font-weight="700">UPFINITY</text>
  </g>

  <line x1="450" y1="46" x2="450" y2="270" stroke="#21262d" stroke-width="1"/>

  <g font-size="13">
    <text x="480" y="64" fill="#8b949e">primary languages tracked</text>
    {lang_block}
  </g>

  <line x1="30" y1="216" x2="870" y2="216" stroke="#21262d" stroke-width="1"/>
  <text x="30" y="240" font-size="12" fill="#484f58">note: public GitHub activity is a small slice of the work — most of it ships</text>
  <text x="30" y="258" font-size="12" fill="#484f58">through UPFINITY client repos and isn't public.</text>
  <text x="30" y="284" font-size="11" fill="#30363d">last synced {synced_at}</text>
</svg>
'''
    return svg


def update_readme_timestamp(readme_path, synced_at):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    marker_start = "<!-- LAST_SYNCED_START -->"
    marker_end = "<!-- LAST_SYNCED_END -->"
    stamp_line = f"{marker_start} last synced: `{synced_at}` {marker_end}"

    if marker_start in content and marker_end in content:
        pre = content.split(marker_start)[0]
        post = content.split(marker_end)[1]
        content = pre + stamp_line + post
    else:
        # marker not found yet — append a small footer line before EOF
        content = content.rstrip() + f"\n\n<div align=\"center\"><sub>{stamp_line}</sub></div>\n"

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    repo_root = os.environ.get("GITHUB_WORKSPACE", ".")
    svg_path = os.path.join(repo_root, "assets", "stats.svg")
    readme_path = os.path.join(repo_root, "README.md")

    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    try:
        stats = fetch_stats()
    except Exception as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    svg = render_svg(stats, synced_at)
    os.makedirs(os.path.dirname(svg_path), exist_ok=True)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    update_readme_timestamp(readme_path, synced_at)
    print("stats.svg and README timestamp updated")


if __name__ == "__main__":
    main()
