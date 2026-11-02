# EGC clouds gallery

A shareable gallery of figures and animations from the EGC cloud and SST work: how submesoscale structure in the East Greenland Current system shapes offshore cloud development.

Live site, once published: https://jcooke188.github.io/egc-clouds-gallery/

Every figure or video can be linked directly. Open it in the gallery and use **Copy link**, which gives a URL ending in `#its-id`.

## What is where

| Path | Purpose |
| --- | --- |
| `index.html`, `gallery.html` | The two pages. You should rarely need to edit these. |
| `content/site.json` | Title, summary, team, links, contact. Edit this to change the landing page. |
| `media/manifest.json` | One entry per figure or video. Written by `tools/add_media.py`. |
| `media/figures/`, `media/videos/`, `media/thumbs/` | Web copies, video previews, thumbnails and posters. |
| `tools/add_media.py` | Adds an item: copies or compresses it, makes thumbnails, records provenance. |
| `tools/check_site.py` | Validates the manifest and file sizes. Also runs on every push through GitHub Actions. |
| `tools/make_hero.py` | Regenerates the schematic band at the top of each page. |

## Publish it (one time)

1. On GitHub, create a **public** repository named `egc-clouds-gallery` under `JCooke188`. Do not add a README, since this folder has one.
2. From this folder:
   ```bash
   git init -b main
   git add .
   git commit -m "Start EGC clouds gallery"
   git remote add origin git@github.com:JCooke188/egc-clouds-gallery.git
   git push -u origin main
   ```
3. On GitHub, open **Settings > Pages**. Under **Build and deployment**, choose **Deploy from a branch**, then branch `main` and folder `/ (root)`, and save.
4. The site appears at the URL above within a few minutes.

The empty `.nojekyll` file tells Pages to serve the files as they are, without running Jekyll.

## Preview locally

The pages load their content with `fetch`, which browsers block for files opened straight from disk. Serve the folder instead:

```bash
python -m http.server 8000
# then open http://localhost:8000
```

## Add a figure or video

You need Pillow (`pip install pillow`). For videos you also need ffmpeg (`conda install -c conda-forge ffmpeg` or `brew install ffmpeg`).

```bash
python tools/add_media.py path/to/cth_over_sst_2024-10.png \
  --title "Cloud-top height over Band 14 BT, October 2024" \
  --caption "Two-kilometre ACHA cloud-top height over GOES-16 Band 14 brightness temperature. Band 14 is not SST; note the cold offset." \
  --tags "GOES-16" "cloud-top height" \
  --data "GOES-16 ABI L2 ACHA2KMF" "GOES-16 ABI L1b Band 14" \
  --code ~/research/abi-greenland/notebooks/goes_cth_over_sst.ipynb \
  --featured

python tools/check_site.py
git add media && git commit -m "Add CTH over BT, Oct 2024" && git push
```

Useful options:

- `--code FILE` records the notebook or script that made the item. If that file is in a git repository, the entry gets a permanent link to it at the current commit. The script warns you if the file has uncommitted changes.
- `--featured` shows the item on the landing page. The six most recent featured items appear there.
- `--date YYYY-MM-DD` sets the item's date; the default is today. Use the date the figure was made, not the date of the data.
- `--replace` overwrites an existing entry with the same id.
- Captions are plain text. Separate paragraphs with a blank line.

To edit or remove an entry later, change `media/manifest.json` directly and delete the matching files in `media/`.

PDF figures cannot be shown in the browser grid. Export a PNG first, for example `pdftoppm -png -r 200 fig.pdf fig`.

## Videos: previews here, full resolution on Zenodo

`add_media.py` re-encodes each video into a web preview: H.264, no audio, at most 1280 px wide, under 20 MB by default. The original stays wherever it is. Do not commit originals to this repository.

To link a full-resolution original:

1. Upload the originals to a Zenodo record. One record per batch or per month of movies keeps this manageable, and you can add files later by publishing a new version.
2. Copy each file's URL from the record (`https://zenodo.org/records/<id>/files/<name>.mp4`) and the record DOI.
3. Pass them when adding the preview:
   ```bash
   python tools/add_media.py cloud_mask_v5_2024-10.mp4 \
     --title "Visible-only cloud mask, October 2024" \
     --full-res-url "https://zenodo.org/records/<id>/files/cloud_mask_v5_2024-10.mp4" \
     --full-res-label Zenodo --doi 10.5281/zenodo.<id>
   ```

Published Zenodo records cannot be deleted, only versioned. Use the Zenodo **sandbox** (sandbox.zenodo.org) for trial uploads, and publish only what you are comfortable having permanently citable.

If a preview is still too large, use `--fps 12` to drop frames or `--target-mb 10` for a tighter budget.

## Limits to keep in mind

| Limit | Value |
| --- | --- |
| Single file, GitHub warning | above 50 MB |
| Single file, GitHub rejection | above 100 MB |
| Published Pages site size | 1 GB |
| Pages bandwidth (soft limit) | about 100 GB per month |
| Git LFS on Pages | not served, so do not use LFS for anything the site displays |

`check_site.py` fails on any file above 50 MB and warns once media passes 800 MB in total.

## Change the landing page

Edit `content/site.json`:

- **Title and summary**: `title`, `short_title`, `summary`. The summary is a list of paragraphs.
- **Team members**: add a `url` to a team member to link their name.
- **Contact**: set `contact.email` to show an address in the footer.

To change the schematic band, edit the constants at the top of `tools/make_hero.py` and run it. The band is a cartoon of the hypothesis, and its caption in `site.json` says so. Keep that caption if the figure stays.
