"""Build the GitHub Pages site from the reports' markdown.

Renders README.md as the home page and each papers/<key>/README.md as papers/<key>/index.html,
copying each paper's images. A figure is written in the markdown as an image linked to a figpack
figure (what GitHub shows); here that image is replaced by the embedded figure, at the height
given for it in the paper's figures.json (default 650 px). Links to figpack figures open in a
new tab.

    .venv/bin/python tools/build_site.py [output dir, default _site]
"""

import html
import json
import re
import shutil
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/magland/encore-reports"
FIGURE_PREFIX = "https://figures.figpack.org/"
DEFAULT_HEIGHT = 650

CSS = """
:root { --fg: #1f2328; --muted: #59636e; --bg: #ffffff; --soft: #f6f8fa; --line: #d1d9e0; --link: #0969da; }
@media (prefers-color-scheme: dark) {
  :root { --fg: #e6edf3; --muted: #9198a1; --bg: #0d1117; --soft: #151b23; --line: #3d444d; --link: #4493f8; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 17px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
header.site, footer.site { max-width: 1100px; margin: 0 auto; padding: 14px 20px; color: var(--muted); font-size: 14px; }
header.site { border-bottom: 1px solid var(--line); }
header.site a { color: var(--fg); font-weight: 600; text-decoration: none; }
footer.site { border-top: 1px solid var(--line); margin-top: 48px; }
main { max-width: 1100px; margin: 0 auto; padding: 8px 20px; }
main > :not(figure) { max-width: 780px; }
a { color: var(--link); }
h1 { font-size: 2em; line-height: 1.25; margin: 0.8em 0 0.5em; }
h2 { margin-top: 1.8em; padding-bottom: 0.2em; border-bottom: 1px solid var(--line); }
h3 { margin-top: 1.5em; }
code { background: var(--soft); padding: 0.1em 0.35em; border-radius: 4px; font-size: 0.88em; }
pre { background: var(--soft); padding: 12px 14px; border-radius: 6px; overflow-x: auto; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; margin: 1em 0; font-size: 0.93em; display: block; overflow-x: auto; }
th, td { border: 1px solid var(--line); padding: 6px 12px; text-align: left; }
th { background: var(--soft); }
img { max-width: 100%; }
figure.figpack { margin: 1.4em 0 0.4em; }
figure.figpack iframe { width: 100%; border: 1px solid var(--line); border-radius: 6px; background: #fff; display: block; }
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<header class="site"><a href="{home}">Encore reports</a> &middot; interactive overviews of <a href="https://encorescience.org/" style="font-weight:normal;color:var(--link)">Encore Science</a> reproduction attempts</header>
<main>
{body}
</main>
<footer class="site">Source of this page: <a href="{source}">{source_name}</a> on GitHub. Figures made with <a href="https://github.com/flatironinstitute/figpack">figpack</a>.</footer>
</body>
</html>
"""

# a paragraph holding only an image linked to a figpack figure
FIGURE_IMAGE = re.compile(
    r'<p><a href="(' + re.escape(FIGURE_PREFIX) + r'[^"]+)"><img alt="([^"]*)" src="[^"]*" ?/?></a></p>'
)
FIGURE_LINK = re.compile(r'<a href="(' + re.escape(FIGURE_PREFIX) + r'[^"]+)">')


def figure_heights(paper_dir: Path) -> dict:
    path = paper_dir / "figures.json"
    if not path.exists():
        return {}
    return {f["url"]: f.get("height", DEFAULT_HEIGHT) for f in json.loads(path.read_text()).values()}


def render(md_path: Path, home: str, heights: dict) -> str:
    text = md_path.read_text()
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])
    m = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    title = re.sub(r"<[^>]+>", "", m.group(1)) if m else "Encore reports"

    def embed(match):
        url, alt = match.group(1), match.group(2)
        height = heights.get(url, DEFAULT_HEIGHT)
        return (f'<figure class="figpack"><iframe src="{url}" height="{height}" title="{alt}" '
                f'loading="lazy" allowfullscreen></iframe></figure>')

    body = FIGURE_IMAGE.sub(embed, body)
    body = FIGURE_LINK.sub(r'<a href="\1" target="_blank" rel="noopener">', body)
    rel = md_path.relative_to(ROOT).as_posix()
    return PAGE.format(title=html.escape(html.unescape(title)), css=CSS, body=body, home=home,
                       source=f"{REPO_URL}/blob/main/{rel}", source_name=rel)


def main(out: Path):
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "index.html").write_text(render(ROOT / "README.md", "./", {}))
    (out / ".nojekyll").write_text("")
    for paper in sorted((ROOT / "papers").iterdir()):
        if not (paper / "README.md").exists():
            continue
        dest = out / "papers" / paper.name
        dest.mkdir(parents=True)
        (dest / "index.html").write_text(render(paper / "README.md", "../../", figure_heights(paper)))
        if (paper / "images").is_dir():
            shutil.copytree(paper / "images", dest / "images")
        print(f"built papers/{paper.name}/")
    print(f"site in {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "_site")
