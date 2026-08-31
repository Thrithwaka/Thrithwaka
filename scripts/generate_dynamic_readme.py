#!/usr/bin/env python3
"""
Regenerates the dynamic parts of README.md directly from live GitHub data:
  - Tech Stack       -> aggregated from every repo's real language bytes
  - Projects         -> every public, non-fork repo, sorted by last push
  - Neural network SVG -> nodes sized by your actual language share, animated with SMIL

Nothing here is hand-written content about a specific project or tool.
If you stop using a language or archive a repo, it drops out on the next run.
Only the "About" section in README.md is left alone -- everything else in the
marked sections is fully replaced on every run.
"""

import os
import re
import sys
import json
import urllib.request

USERNAME = "Thrithwaka"
API = "https://api.github.com"
TOKEN = os.environ.get("GH_TOKEN", "")

GREEN_SHADES = ["0d4429", "1b4332", "2d6a4f", "40916c", "52b788", "74c69d"]


def api_get(path):
    req = urllib.request.Request(f"{API}{path}")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{USERNAME}-readme-bot")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_all_repos():
    repos, page = [], 1
    while True:
        batch = api_get(f"/users/{USERNAME}/repos?per_page=100&page={page}&type=owner")
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return [r for r in repos if not r.get("fork") and not r.get("private")]


def get_language_totals(repos):
    totals = {}
    for r in repos:
        try:
            langs = api_get(f"/repos/{USERNAME}/{r['name']}/languages")
        except Exception:
            continue
        for lang, byte_count in langs.items():
            totals[lang] = totals.get(lang, 0) + byte_count
    return dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))


def render_tech_stack(lang_totals):
    total = sum(lang_totals.values()) or 1
    rows = []
    for i, (lang, byte_count) in enumerate(list(lang_totals.items())[:12]):
        pct = round(100 * byte_count / total, 1)
        color = GREEN_SHADES[i % len(GREEN_SHADES)]
        badge = (
            f'<img src="https://img.shields.io/badge/{lang.replace(" ", "%20")}'
            f'-{pct}%25-{color}?style=for-the-badge" />'
        )
        rows.append(badge)
    body = "\n  ".join(rows)
    return (
        "<!-- Auto-generated from real per-repo language byte counts via the GitHub API. -->\n"
        f"<p>\n  {body}\n</p>\n"
        "<sub>Percentages are each language's live share of total code across all public repos.</sub>"
    )


def render_projects(repos):
    repos = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)
    lines = [
        "<!-- Auto-generated: every public, non-fork repo, sorted by most recently pushed. -->",
        "| Project | Description | Primary Language | Stars | Last Push |",
        "|---|---|---|---|---|",
    ]
    for r in repos:
        desc = (r.get("description") or "—").replace("|", "-")
        lang = r.get("language") or "—"
        lines.append(
            f"| [{r['name']}]({r['html_url']}) | {desc} | {lang} | "
            f"{r['stargazers_count']} | {r['pushed_at'][:10]} |"
        )
    return "\n".join(lines)


def render_neural_svg(lang_totals):
    top = list(lang_totals.items())[:9]
    total = sum(v for _, v in top) or 1
    cx, cy, radius = 420, 260, 190
    import math

    nodes_svg, edges_svg = [], []
    n = max(len(top), 1)
    for i, (lang, byte_count) in enumerate(top):
        angle = (2 * math.pi * i) / n
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        pct = byte_count / total
        r = 14 + 26 * pct
        color = GREEN_SHADES[i % len(GREEN_SHADES)]
        dur = round(2.4 + i * 0.15, 2)
        edges_svg.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="#52b788" stroke-width="1.4" stroke-opacity="0.35">'
            f'<animate attributeName="stroke-opacity" values="0.1;0.7;0.1" '
            f'dur="{dur}s" repeatCount="indefinite" /></line>'
        )
        nodes_svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#{color}" fill-opacity="0.85">'
            f'<animate attributeName="r" values="{r:.1f};{r*1.15:.1f};{r:.1f}" '
            f'dur="{dur}s" repeatCount="indefinite" /></circle>'
            f'<text x="{x:.1f}" y="{y+4:.1f}" text-anchor="middle" '
            f'font-family="JetBrains Mono, monospace" font-size="12" fill="#ffffff">{lang}</text>'
        )

    core = (
        f'<circle cx="{cx}" cy="{cy}" r="34" fill="#081c15" stroke="#52b788" stroke-width="2">'
        f'<animate attributeName="r" values="34;40;34" dur="2s" repeatCount="indefinite" />'
        f'</circle>'
        f'<text x="{cx}" y="{cy+5}" text-anchor="middle" font-family="JetBrains Mono, monospace" '
        f'font-size="13" fill="#74c69d">Thrithwaka</text>'
    )

    svg = f'''<svg width="840" height="520" viewBox="0 0 840 520" xmlns="http://www.w3.org/2000/svg">
  <rect width="840" height="520" fill="#0d1117" />
  {"".join(edges_svg)}
  {core}
  {"".join(nodes_svg)}
</svg>'''
    return svg


def replace_section(readme, marker, content):
    pattern = re.compile(
        rf"(<!--START_SECTION:{marker}-->)(.*?)(<!--END_SECTION:{marker}-->)",
        re.DOTALL,
    )
    if not pattern.search(readme):
        print(f"WARNING: markers for '{marker}' not found in README.md", file=sys.stderr)
        return readme
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(3)}", readme)


def main():
    repos = get_all_repos()
    lang_totals = get_language_totals(repos)

    os.makedirs("assets", exist_ok=True)
    with open("assets/neural-network.svg", "w") as f:
        f.write(render_neural_svg(lang_totals))

    with open("README.md") as f:
        readme = f.read()

    readme = replace_section(readme, "techstack", render_tech_stack(lang_totals))
    readme = replace_section(readme, "projects", render_projects(repos))

    with open("README.md", "w") as f:
        f.write(readme)


if __name__ == "__main__":
    main()
