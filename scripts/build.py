#!/usr/bin/env python3
"""Produce a self-contained index plus JSON endpoints for hourly refresh."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DIST = ROOT / "dist"


def build():
    snapshot = json.loads((SITE / "data/snapshot.json").read_text(encoding="utf-8"))
    learn = json.loads((SITE / "data/learn.json").read_text(encoding="utf-8"))
    if snapshot.get("schemaVersion") != 1 or len(snapshot.get("assets", [])) != 25:
        raise ValueError("snapshot validation failed")
    if len(learn.get("topics", [])) != 6:
        raise ValueError("learning content missing")
    html = (SITE / "index.html").read_text(encoding="utf-8")
    css = (SITE / "assets/style.css").read_text(encoding="utf-8")
    js = (SITE / "assets/app.js").read_text(encoding="utf-8")
    bootstrap = json.dumps({"snapshot": snapshot, "learn": learn}, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    bootstrap = bootstrap.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = html.replace('<link rel="stylesheet" href="./assets/style.css">', f"<style>{css}</style>")
    html = html.replace("<!--BOOTSTRAP-->", f"<script>window.__INSIGHT__={bootstrap};</script>")
    html = html.replace('<script src="./assets/app.js" defer></script>', f"<script>{js}</script>")
    DIST.mkdir(exist_ok=True)
    (DIST / "index.html").write_text(html, encoding="utf-8")
    (DIST / ".nojekyll").touch()
    (DIST / "data").mkdir(exist_ok=True)
    for name in ("snapshot.json", "learn.json", "events.json"):
        shutil.copyfile(SITE / "data" / name, DIST / "data" / name)
    print(f"Built {DIST / 'index.html'} ({len(html.encode()):,} bytes).")


if __name__ == "__main__":
    build()
