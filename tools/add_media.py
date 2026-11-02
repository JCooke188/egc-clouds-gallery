#!/usr/bin/env python3
"""Add a figure or video to the gallery.

Figures (png, jpg, webp, gif, svg) are copied into media/figures/ and get a
WebP thumbnail. Videos (mp4, mov, m4v, mkv, avi, webm) are re-encoded into a
small web preview (H.264, no audio, faststart) in media/videos/ with a poster
frame; keep the full-resolution original elsewhere (e.g. Zenodo) and pass its
link with --full-res-url.

Every entry can record the notebook or script that produced it. Pass
--code path/to/notebook.ipynb and the script looks up the git commit and
remote of that file's repository and writes a permanent link.

Examples
  python tools/add_media.py ~/figs/cth_over_sst_2024-10.png \\
      --title "Cloud-top height over Band 14 BT, October 2024" \\
      --caption "Two-kilometre ACHA cloud-top height ..." \\
      --tags "GOES-16" "cloud-top height" --data "GOES-16 ABI L2 ACHA2KMF" \\
      --code ~/research/abi-greenland/notebooks/goes_cth_over_sst.ipynb --featured

  python tools/add_media.py ~/movies/cloud_mask_v5_2024-10.mp4 \\
      --title "Visible-only cloud mask, October 2024" \\
      --full-res-url https://zenodo.org/records/XXXXXXX/files/cloud_mask_v5_2024-10.mp4 \\
      --full-res-label Zenodo

Requires Pillow (pip install pillow) and, for videos, ffmpeg and ffprobe.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "media" / "manifest.json"
FIG_DIR = ROOT / "media" / "figures"
VID_DIR = ROOT / "media" / "videos"
THUMB_DIR = ROOT / "media" / "thumbs"

FIG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
VID_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}

GITHUB_WARN_MB = 50      # GitHub warns above 50 MB and rejects files above 100 MB
THUMB_WIDTH = 800

# Encoding ladder for video previews: (max width px, x264 CRF). Tried in order
# until the preview fits under --target-mb.
LADDER = [(1280, 26), (1280, 30), (960, 30), (960, 34), (720, 34), (640, 38)]


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def mb(path: Path) -> float:
    return path.stat().st_size / 1e6


def slugify(text: str, maxlen: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:maxlen].rstrip("-") or "item"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"items": []}
    return json.loads(MANIFEST.read_text())


def save_manifest(data: dict) -> None:
    data["items"].sort(key=lambda i: (i.get("date", ""), i["id"]), reverse=True)
    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def run(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        die(f"{' '.join(cmd[:2])} failed:\n{res.stderr.strip()[-2000:]}")
    return res.stdout


# Provenance -----------------------------------------------------------------

def git(path: Path, *args: str) -> str | None:
    res = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else None


def remote_to_https(url: str) -> str | None:
    m = re.match(r"(?:git@|ssh://git@)([^:/]+)[:/](.+?)(?:\.git)?$", url)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}"
    m = re.match(r"(https?://.+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def code_provenance(code_file: Path) -> dict:
    code_file = code_file.expanduser().resolve()
    if not code_file.exists():
        die(f"--code file not found: {code_file}")
    top = git(code_file.parent, "rev-parse", "--show-toplevel")
    if not top:
        print(f"note: {code_file.name} is not in a git repository; recording the file name only")
        return {"path": code_file.name}
    relpath = code_file.relative_to(Path(top)).as_posix()
    commit = git(Path(top), "rev-parse", "HEAD")
    info = {"path": relpath, "commit": commit[:10] if commit else None}
    if git(Path(top), "status", "--porcelain", "--", relpath):
        print(f"warning: {relpath} has uncommitted changes; the link points to the last commit, "
              "not the version that made this figure. Commit first for an exact record.")
    remote = git(Path(top), "config", "--get", "remote.origin.url")
    base = remote_to_https(remote) if remote else None
    if base and commit:
        info["url"] = f"{base}/blob/{commit}/{relpath}"
    return {k: v for k, v in info.items() if v}


# Figures --------------------------------------------------------------------

def add_figure(src: Path, item_id: str) -> dict:
    ext = src.suffix.lower()
    dest = FIG_DIR / f"{item_id}{ext}"
    shutil.copy2(src, dest)
    entry = {"type": "figure", "file": rel(dest)}

    if ext == ".svg":
        entry["thumb"] = rel(dest)
    else:
        from PIL import Image
        thumb = THUMB_DIR / f"{item_id}.webp"
        with Image.open(dest) as im:
            entry["width"], entry["height"] = im.size
            im.seek(0)
            im = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA") else im.convert("RGB")
            if im.width > THUMB_WIDTH:
                im = im.resize((THUMB_WIDTH, round(im.height * THUMB_WIDTH / im.width)), Image.LANCZOS)
            im.save(thumb, "WEBP", quality=82, method=6)
        entry["thumb"] = rel(thumb)

    size = mb(dest)
    if size > 10:
        print(f"warning: {dest.name} is {size:.1f} MB. Consider exporting at lower dpi or as WebP; "
              "large figures load slowly for anyone opening the gallery.")
    return entry


# Videos ---------------------------------------------------------------------

def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height,r_frame_rate:format=duration",
               "-of", "json", str(path)])
    info = json.loads(out)
    s = info["streams"][0]
    num, den = (s.get("r_frame_rate") or "0/1").split("/")
    return {"width": s["width"], "height": s["height"],
            "fps": float(num) / float(den) if float(den) else None,
            "duration": float(info["format"].get("duration", 0))}


def encode(src: Path, dest: Path, width: int, crf: int, fps: float | None) -> None:
    vf = f"scale='trunc(min({width},iw)/2)*2':-2:flags=lanczos"
    if fps:
        vf += f",fps={fps}"
    vf += ",format=yuv420p"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-an", "-vf", vf,
         "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
         "-profile:v", "high", "-movflags", "+faststart", str(dest)])


def add_video(src: Path, item_id: str, target_mb: float, fps: float | None, poster_at: float | None) -> dict:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            die(f"{tool} is required for videos (conda install ffmpeg, or brew install ffmpeg)")

    info = probe(src)
    dest = VID_DIR / f"{item_id}.mp4"
    for width, crf in LADDER:
        encode(src, dest, width, crf, fps)
        size = mb(dest)
        print(f"  preview at <= {width}px, CRF {crf}: {size:.1f} MB")
        if size <= target_mb:
            break
    else:
        print(f"warning: smallest preview is {mb(dest):.1f} MB, above the {target_mb} MB target. "
              "Try --fps to drop frames, or trim the clip.")
    if mb(dest) > GITHUB_WARN_MB:
        die(f"{dest.name} is {mb(dest):.1f} MB; GitHub warns above {GITHUB_WARN_MB} MB. Trim or lower --fps.")

    out = probe(dest)
    t = poster_at if poster_at is not None else 0.25 * out["duration"]
    t = max(0.0, min(t, max(out["duration"] - 0.1, 0.0)))
    poster_jpg = THUMB_DIR / f"{item_id}-poster.jpg"
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(dest),
         "-frames:v", "1", "-q:v", "3", str(poster_jpg)])

    from PIL import Image
    poster = THUMB_DIR / f"{item_id}-poster.webp"
    thumb = THUMB_DIR / f"{item_id}.webp"
    with Image.open(poster_jpg) as im:
        im = im.convert("RGB")
        im.save(poster, "WEBP", quality=85, method=6)
        if im.width > THUMB_WIDTH:
            im = im.resize((THUMB_WIDTH, round(im.height * THUMB_WIDTH / im.width)), Image.LANCZOS)
        im.save(thumb, "WEBP", quality=82, method=6)
    poster_jpg.unlink()

    return {"type": "video", "file": rel(dest), "poster": rel(poster), "thumb": rel(thumb),
            "width": out["width"], "height": out["height"],
            "duration_s": round(out["duration"], 1),
            "source_resolution": f"{info['width']}x{info['height']}"}


# Main -----------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Add a figure or video to the gallery.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("file", type=Path, help="figure or video to add")
    p.add_argument("--title", required=True)
    p.add_argument("--caption", default="", help="plain text; separate paragraphs with a blank line")
    p.add_argument("--alt", default="", help="short description for screen readers (defaults to the title)")
    p.add_argument("--date", default=dt.date.today().isoformat(), help="YYYY-MM-DD (default: today)")
    p.add_argument("--tags", nargs="*", default=[])
    p.add_argument("--data", nargs="*", default=[], dest="data_sources",
                   help="data products used, e.g. 'GOES-16 ABI L2 ACHA2KMF' 'ERA5'")
    p.add_argument("--code", type=Path, help="notebook or script that produced this item")
    p.add_argument("--full-res-url", help="link to the full-resolution original")
    p.add_argument("--full-res-label", help="where it lives, e.g. Zenodo")
    p.add_argument("--doi", help="DOI of the full-resolution record, e.g. 10.5281/zenodo.1234567")
    p.add_argument("--featured", action="store_true", help="show on the landing page")
    p.add_argument("--id", help="custom id (default: date plus slug of the title)")
    p.add_argument("--replace", action="store_true", help="overwrite an existing entry with the same id")
    p.add_argument("--target-mb", type=float, default=20, help="video preview size target (default 20)")
    p.add_argument("--fps", type=float, help="cap video preview frame rate")
    p.add_argument("--poster-at", type=float, help="time in seconds for the video poster frame")
    a = p.parse_args()

    src = a.file.expanduser().resolve()
    if not src.exists():
        die(f"file not found: {src}")
    try:
        dt.date.fromisoformat(a.date)
    except ValueError:
        die("--date must be YYYY-MM-DD")

    ext = src.suffix.lower()
    if ext not in FIG_EXT | VID_EXT:
        hint = " Export a PNG (e.g. pdftoppm -png -r 200) to show a PDF figure." if ext == ".pdf" else ""
        die(f"unsupported file type {ext}.{hint}")

    item_id = a.id or f"{a.date}-{slugify(a.title)}"
    data = load_manifest()
    existing = [i for i in data["items"] if i["id"] == item_id]
    if existing and not a.replace:
        die(f"an entry with id '{item_id}' exists; pass --replace to overwrite or --id to choose another")
    data["items"] = [i for i in data["items"] if i["id"] != item_id]

    for d in (FIG_DIR, VID_DIR, THUMB_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print(f"adding {src.name} as {item_id}")
    media = add_video(src, item_id, a.target_mb, a.fps, a.poster_at) if ext in VID_EXT else add_figure(src, item_id)

    entry = {"id": item_id, "title": a.title, "date": a.date, **media,
             "caption": a.caption, "alt": a.alt or None, "tags": a.tags,
             "data_sources": a.data_sources, "featured": a.featured or None}
    if a.code:
        entry["code"] = code_provenance(a.code)
    if a.full_res_url or a.doi:
        entry["full_res"] = {k: v for k, v in
                             {"url": a.full_res_url, "label": a.full_res_label, "doi": a.doi}.items() if v}
    entry["added"] = dt.datetime.now().isoformat(timespec="seconds")
    entry = {k: v for k, v in entry.items() if v not in (None, "", [])}

    data["items"].append(entry)
    save_manifest(data)
    print(f"done: {entry['file']} ({mb(ROOT / entry['file']):.1f} MB). Review media/manifest.json, then commit.")


if __name__ == "__main__":
    main()
