"""Render the public Vercel pages without importing the private Flask service."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

root = Path(__file__).resolve().parent
out = root / "public-pages"
out.mkdir(exist_ok=True)
template = Environment(loader=FileSystemLoader(root / "templates"),
                       autoescape=select_autoescape()).get_template("page.html")
for file, page in [("index", "/"), ("map", "/map"), ("docs", "/docs"), ("login", "offline")]:
    (out / f"{file}.html").write_text(template.render(page=page, disconnected=True, rows=[]), encoding="utf-8")
