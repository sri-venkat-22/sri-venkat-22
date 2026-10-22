"""Render an animated, monochrome 31-day contribution graph as SVG.

Env:
  GITHUB_TOKEN  token for the GitHub GraphQL API (Actions' built-in token works)
  USERNAME      GitHub login
  DISPLAY_NAME  name shown in the title (default "Sri Venkat")
  OUT           output path (default dist/activity-graph.svg)
  DAYS          window size (default 31)
"""
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

USER = os.environ.get("USERNAME", "sri-venkat-22")
DISPLAY = os.environ.get("DISPLAY_NAME", "Sri Venkat")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT", "dist/activity-graph.svg")
DAYS = int(os.environ.get("DAYS", "31"))

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def fetch(days):
    to = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0)
    frm = (to - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0)
    body = json.dumps({"query": QUERY, "variables": {
        "login": USER, "from": frm.isoformat(), "to": to.isoformat()}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
        "User-Agent": "activity-graph"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days_ = [d for w in weeks for d in w["contributionDays"]]
    days_.sort(key=lambda d: d["date"])
    return [(d["date"], d["contributionCount"]) for d in days_][-days:]


def nice_max(v):
    """Top of the y-axis, chosen so 4 gridlines land on whole numbers."""
    raw = max(1, math.ceil(v / 4))
    for step in (1, 2, 3, 4, 5, 10, 15, 20, 25, 50, 100, 250, 500):
        if step >= raw:
            return step * 4
    return raw * 4


def render(series):
    W, H = 1000, 340
    L, R, T, B = 64, 28, 64, 60
    pw, ph = W - L - R, H - T - B
    counts = [c for _, c in series]
    ymax = nice_max(max(counts) if counts else 0)
    n = len(series)
    xs = [L + pw * i / (n - 1) for i in range(n)]
    ys = [T + ph - ph * c / ymax for c in counts]
    pts = list(zip(xs, ys))
    line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{line} L{xs[-1]:.1f},{T + ph} L{xs[0]:.1f},{T + ph} Z"
    length = sum(math.dist(pts[i], pts[i + 1]) for i in range(n - 1))
    total = sum(counts)
    draw = 2.4  # seconds for the line to draw in

    grid, ylab = [], []
    for k in range(5):
        v = ymax * k / 4
        y = T + ph - ph * k / 4
        grid.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke="#1f1f1f" stroke-width="1"/>')
        ylab.append(f'<text x="{L - 12}" y="{y + 4:.1f}" text-anchor="end">{int(v)}</text>')

    xlab = [f'<text x="{x:.1f}" y="{T + ph + 22}" text-anchor="middle">{int(d[8:])}</text>'
            for x, (d, _) in zip(xs, series)]

    dots = []
    for i, ((x, y), c) in enumerate(zip(pts, counts)):
        begin = draw * i / (n - 1)
        r = 4.2 if c else 3
        fill = "#ffffff" if c else "#000000"
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="#ffffff" stroke-width="1.6" opacity="0">'
            f'<title>{series[i][0]}: {c} contribution{"s" if c != 1 else ""}</title>'
            f'<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" dur=".25s" fill="freeze"/></circle>')

    start = datetime.fromisoformat(series[0][0]).strftime("%b %d")
    end = datetime.fromisoformat(series[-1][0]).strftime("%b %d, %Y")

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{USER} contribution graph, last {n} days">
  <defs>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".28"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="reveal"><rect x="{L}" y="0" height="{H}" width="0">
      <animate attributeName="width" from="0" to="{pw}" dur="{draw}s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".4 0 .2 1"/>
    </rect></clipPath>
  </defs>
  <style>
    text {{ font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; fill: #8b949e; font-size: 11px; }}
    .title {{ fill: #ffffff; font-size: 17px; font-weight: 600; }}
    .sub {{ fill: #8b949e; font-size: 12px; }}
    .axis {{ fill: #c9d1d9; font-size: 12px; }}
  </style>
  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="8" fill="#000000" stroke="#30363d"/>
  <text x="{W / 2}" y="32" text-anchor="middle" class="title">{DISPLAY}&#8217;s Contribution Graph</text>
  <text x="{W / 2}" y="50" text-anchor="middle" class="sub">{start} &#8211; {end} &#183; {total} contribution{"s" if total != 1 else ""}</text>
  {"".join(grid)}
  {"".join(ylab)}
  {"".join(xlab)}
  <text x="{W / 2}" y="{H - 12}" text-anchor="middle" class="axis">Days</text>
  <text x="18" y="{T + ph / 2}" text-anchor="middle" class="axis" transform="rotate(-90 18 {T + ph / 2})">Contributions</text>
  <path d="{area}" fill="url(#area)" clip-path="url(#reveal)"/>
  <path d="{line}" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"
        stroke-dasharray="{length:.1f}" stroke-dashoffset="{length:.1f}">
    <animate attributeName="stroke-dashoffset" from="{length:.1f}" to="0" dur="{draw}s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".4 0 .2 1"/>
  </path>
  {"".join(dots)}
</svg>
'''


if __name__ == "__main__":
    if os.environ.get("DEMO"):
        import random
        random.seed(7)
        today = datetime.now(timezone.utc).date()
        series = [((today - timedelta(days=DAYS - 1 - i)).isoformat(),
                   random.choice([0, 0, 0, 1, 2, 3, 5, 8])) for i in range(DAYS)]
    else:
        if not TOKEN:
            sys.exit("GITHUB_TOKEN is not set")
        series = fetch(DAYS)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(series))
    print(f"wrote {OUT} ({len(series)} days, {sum(c for _, c in series)} contributions)")
