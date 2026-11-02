#!/usr/bin/env python3
"""Check the site before it is published. Standard library only.

Fails (exit 1) on: invalid JSON, missing required fields, duplicate ids,
referenced files that do not exist, files over 50 MB, bad dates.
Warns on: total media approaching the 1 GB GitHub Pages limit, missing captions.

Run locally with:  python tools/check_site.py
"""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE_LIMIT_MB = 50
SITE_WARN_MB = 800

errors, warnings = [], []


def load(path):
    try:
        return json.loads((ROOT / path).read_text())
    except Exception as e:  # noqa: BLE001
        errors.append(f"{path}: {e}")
        return None


site = load("content/site.json")
if site is not None:
    for key in ("title", "summary", "team"):
        if not site.get(key):
            errors.append(f"content/site.json: missing '{key}'")

manifest = load("media/manifest.json")
items = (manifest or {}).get("items", [])
seen = set()
for n, item in enumerate(items):
    where = f"manifest item {n} ({item.get('id', 'no id')})"
    for key in ("id", "type", "title", "date", "file"):
        if not item.get(key):
            errors.append(f"{where}: missing '{key}'")
    if item.get("id") in seen:
        errors.append(f"{where}: duplicate id")
    seen.add(item.get("id"))
    if item.get("type") not in ("figure", "video"):
        errors.append(f"{where}: type must be 'figure' or 'video'")
    try:
        dt.date.fromisoformat(item.get("date", ""))
    except ValueError:
        errors.append(f"{where}: date must be YYYY-MM-DD")
    for key in ("file", "thumb", "poster"):
        if item.get(key) and not (ROOT / item[key]).exists():
            errors.append(f"{where}: {key} not found: {item[key]}")
    if not item.get("caption"):
        warnings.append(f"{where}: no caption")

total = 0
for f in (ROOT / "media").rglob("*"):
    if f.is_file():
        size = f.stat().st_size / 1e6
        total += size
        if size > FILE_LIMIT_MB:
            errors.append(f"{f.relative_to(ROOT)}: {size:.1f} MB exceeds {FILE_LIMIT_MB} MB")
if total > SITE_WARN_MB:
    warnings.append(f"media totals {total:.0f} MB; GitHub Pages sites are limited to 1 GB")

for w in warnings:
    print(f"warning: {w}")
for e in errors:
    print(f"error: {e}")
print(f"{len(items)} items, {total:.1f} MB of media, {len(errors)} errors, {len(warnings)} warnings")
sys.exit(1 if errors else 0)
