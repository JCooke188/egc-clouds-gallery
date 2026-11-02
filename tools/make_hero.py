#!/usr/bin/env python3
"""Generate assets/img/hero.svg, the schematic band used at the top of the site.

The picture is a cartoon of the project's core observation, not data:
sea ice and cold shelf water on the left stay clear, a meandering front
separates them from warmer offshore water, and cloud streets form only on
the warm side. A detached warm eddy on the cold side carries its own small
cloud patch.

Edit the constants below and rerun:  python tools/make_hero.py
"""
import math
import pathlib
import random

W, H = 1600, 520
SEED = 7
FRONT_X = 700          # mean x position of the SST front
ICE_X = 150            # mean x position of the ice edge
COLD = ("#0F2736", "#173D4F")   # cold shelf water, top to bottom
WARM = ("#4F4C47", "#7A5A48")   # warm offshore water, left to right
ICE = "#E3EAED"
CLOUD = "#F7F9FA"

rng = random.Random(SEED)
out = pathlib.Path(__file__).resolve().parents[1] / "assets" / "img" / "hero.svg"


def front_x(y):
    return FRONT_X + 46 * math.sin(y / 88.0) + 22 * math.sin(y / 31.0 + 1.3)


def ice_x(y):
    return (ICE_X + 18 * math.sin(y / 61.0 + 0.4) + 9 * math.sin(y / 23.0 + 2.1)
            + 5 * math.sin(y / 7.3) + 3 * math.sin(y / 3.1 + 0.7))


ys = range(-10, H + 11, 3)
front_pts = [(front_x(y), y) for y in ys]
ice_pts = [(ice_x(y), y) for y in ys]


def poly(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


warm_poly = front_pts + [(W + 10, H + 10), (W + 10, -10)]
ice_poly = [(-10, -10)] + ice_pts + [(-10, H + 10)]

# Sea-ice floes scattered just offshore of the ice edge
floes = []
for _ in range(160):
    y = rng.uniform(0, H)
    x = ice_x(y) + abs(rng.gauss(0, 70))
    if x > front_x(y) - 120:
        continue
    r = rng.uniform(2, 9) * max(0.35, 1 - (x - ICE_X) / 260)
    n = rng.randint(5, 7)
    a0 = rng.uniform(0, math.pi)
    pts = [(x + r * rng.uniform(0.6, 1.0) * math.cos(a0 + 2 * math.pi * k / n),
            y + r * rng.uniform(0.6, 1.0) * math.sin(a0 + 2 * math.pi * k / n)) for k in range(n)]
    floes.append(f'<polygon points="{poly(pts)}" fill="{ICE}" opacity="{rng.uniform(0.55, 0.9):.2f}"/>')

# Warm eddy detached on the cold side of the front
EDDY = (FRONT_X - 150, 372, 46)

# Cloud streets: rows aligned with an off-ice wind, only over warm water.
clouds = []
angle = 9  # degrees, wind direction relative to the image x axis
for row_y in range(-40, H + 60, 30):
    x = FRONT_X - 40
    while x < W + 80:
        y = row_y + (x - FRONT_X) * math.tan(math.radians(angle)) * 0.35
        downstream = (x - front_x(y)) / (W - FRONT_X)
        rx = rng.uniform(24, 70) * (0.7 + 0.8 * max(downstream, 0))
        if x - rx > front_x(y) + 6 and rng.random() < 0.35 + 0.6 * min(downstream, 1):
            ry = rng.uniform(5, 10) * (0.8 + 0.7 * downstream)
            op = min(0.95, 0.35 + 0.7 * downstream) * rng.uniform(0.75, 1.0)
            clouds.append(
                f'<ellipse cx="{x:.0f}" cy="{y + rng.gauss(0, 3):.0f}" rx="{rx:.0f}" ry="{ry:.0f}" '
                f'opacity="{op:.2f}" transform="rotate({angle} {x:.0f} {y:.0f})"/>')
        x += rng.uniform(40, 95)

# A small cloud patch over the warm eddy
ex, ey, er = EDDY
eddy_clouds = []
for _ in range(7):
    cx = ex + rng.gauss(14, 14)
    cy = ey + rng.gauss(0, 12)
    eddy_clouds.append(
        f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rng.uniform(10, 22):.0f}" ry="{rng.uniform(4, 7):.0f}" '
        f'opacity="{rng.uniform(0.45, 0.7):.2f}" transform="rotate({angle} {cx:.0f} {cy:.0f})"/>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice" role="img" aria-labelledby="t d">
<title id="t">Schematic of clouds over the East Greenland Current</title>
<desc id="d">Sea ice and cold shelf water on the left stay clear of cloud. Across a meandering front, cloud streets form over warmer offshore water. A detached warm eddy on the cold side carries a small patch of cloud.</desc>
<defs>
  <linearGradient id="cold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{COLD[0]}"/><stop offset="1" stop-color="{COLD[1]}"/></linearGradient>
  <linearGradient id="warm" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{WARM[0]}"/><stop offset="1" stop-color="{WARM[1]}"/></linearGradient>
  <filter id="soft" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="4.5"/></filter>
  <filter id="edge" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="1.6"/></filter>
</defs>
<rect width="{W}" height="{H}" fill="url(#cold)"/>
<polygon points="{poly(warm_poly)}" fill="url(#warm)" filter="url(#edge)"/>
<polyline points="{poly(front_pts)}" fill="none" stroke="#B98F6A" stroke-width="1.5" opacity="0.4"/>
<ellipse cx="{ex}" cy="{ey}" rx="{er * 1.15:.0f}" ry="{er * 0.9:.0f}" fill="{WARM[0]}" filter="url(#edge)" transform="rotate(-20 {ex} {ey})"/>
<g>{"".join(floes)}</g>
<polygon points="{poly(ice_poly)}" fill="{ICE}"/>
<g fill="{CLOUD}" filter="url(#soft)">{"".join(clouds)}{"".join(eddy_clouds)}</g>
</svg>
'''

out.write_text(svg)
print(f"wrote {out} ({len(svg) / 1024:.1f} KiB, {len(clouds)} cloud elements)")
