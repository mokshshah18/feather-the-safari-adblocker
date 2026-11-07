#!/usr/bin/env python3
"""Draw the README figures in docs/ from the compiled rule list.

Each figure is a self-contained SVG on a fixed dark card, so it renders the
same in GitHub's light and dark themes and needs no external fonts or scripts.
Counts come from ContentBlocker/blockerList.json and rules/domains.txt, so
the pictures cannot drift from the shipped rules. Run after `make rules`.
"""
import json
import pathlib
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LIST = ROOT / "ContentBlocker" / "blockerList.json"

# Palette: brand navy surface, dataviz "dark" text and series steps.
SURFACE = "#142434"
INK = "#f0efec"
INK2 = "#c3c2b7"
MUTED = "#898781"
FEATHER = "#f4f1e8"
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500"]  # categorical slots 1-4
LABEL_ON = ["#ffffff", "#ffffff", "#ffffff", "#0b0b0b"]  # ink inside each fill
DROP, PASS = "#e66767", "#199e70"  # outcome marks in the flow diagram
GOOD, WARN, NO = "#0ca30c", "#fab219", "#d03b3b"  # status palette (fixed)
FONT = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"


def tw(s: str, size: float) -> float:
    """Rough text width; generous so chips never clip on wide system fonts."""
    return len(s) * size * 0.58


class Svg:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'font-family="{FONT}">',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="{INK2}"/></marker></defs>',
            f'<rect width="{w}" height="{h}" rx="24" fill="{SURFACE}"/>',
        ]

    def text(self, x, y, s, size=14, fill=INK, weight="normal", anchor="start", **extra):
        attrs = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in extra.items())
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{attrs}>{escape(s)}</text>')

    def box(self, x, y, w, h, rx=12, opacity=0.06):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="#ffffff" '
            f'fill-opacity="{opacity}" stroke="#ffffff" stroke-opacity="0.14"/>')

    def arrow(self, points):
        pts = " ".join(f"{x},{y}" for x, y in points)
        self.parts.append(
            f'<polyline points="{pts}" fill="none" stroke="{INK2}" stroke-width="2" '
            'stroke-linejoin="round" marker-end="url(#arrow)"/>')

    def mark(self, cx, cy, kind, r=9):
        """A status mark: filled circle with a check, a half-disc, or a cross."""
        color = {"ok": GOOD, "part": WARN, "no": NO, "drop": DROP, "pass": PASS}[kind]
        ink = "#0b0b0b" if kind == "part" else "#ffffff"
        self.parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')
        if kind in ("ok", "pass"):
            self.parts.append(
                f'<path d="M{cx - 4.5} {cy} l3.2 3.2 l5.8 -6.4" fill="none" stroke="{ink}" '
                'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>')
        elif kind == "part":
            self.parts.append(
                f'<path d="M{cx} {cy - 5.5} a5.5 5.5 0 0 1 0 11 z" fill="{ink}"/>'
                f'<circle cx="{cx}" cy="{cy}" r="5.5" fill="none" stroke="{ink}" stroke-width="1.6"/>')
        else:
            self.parts.append(
                f'<path d="M{cx - 3.8} {cy - 3.8} l7.6 7.6 M{cx + 3.8} {cy - 3.8} l-7.6 7.6" '
                f'stroke="{ink}" stroke-width="2.2" stroke-linecap="round"/>')

    def feather(self, cx, cy, scale=1.0, opacity=1.0):
        """The app icon's feather: a tilted leaf with a carved spine and quill."""
        hl, hw = 95 * scale, 37 * scale
        s = hl / 0.27  # the icon generator's canvas size, for the notch geometry
        sp = 4 * scale
        notches = ""
        for frac in (0.15, 0.45):
            y = -hl * frac
            notches += (f'<polygon points="{-hw * 1.05:.1f},{y:.1f} {-hw * 0.35:.1f},{y + s * 0.05:.1f} '
                        f'{-hw * 1.05:.1f},{y + s * 0.07:.1f}" fill="{SURFACE}"/>')
        self.parts.append(
            f'<g transform="translate({cx} {cy}) rotate(-32)" opacity="{opacity}">'
            f'<ellipse rx="{hw:.1f}" ry="{hl:.1f}" fill="{FEATHER}"/>'
            f'<rect x="{-sp}" y="{-hl * 0.92:.1f}" width="{2 * sp}" height="{hl * 1.90:.1f}" rx="{sp}" fill="{SURFACE}"/>'
            f'<rect x="{-sp}" y="{hl * 0.85:.1f}" width="{2 * sp}" height="{hl * 0.45:.1f}" rx="{sp}" fill="{FEATHER}"/>'
            f'{notches}</g>')

    def chip(self, x, y, label, kind, h=36):
        w = 16 + 18 + 10 + tw(label, 15) + 16
        self.box(x, y, w, h, rx=h / 2)
        self.mark(x + 16 + 9, y + h / 2, kind)
        self.text(x + 16 + 18 + 10, y + h / 2 + 5, label, 15, INK)
        return w

    def write(self, name):
        self.parts.append("</svg>")
        (DOCS / name).write_text("\n".join(self.parts) + "\n")
        print(f"wrote docs/{name} ({self.w}x{self.h})")


def stats():
    rules = json.loads(LIST.read_text())
    blocks = [r for r in rules if r["action"]["type"] == "block"]
    cosmetic = [r for r in rules if r["action"]["type"] == "css-display-none"]
    hosts = {"[block]": 0, "[block-third-party]": 0}
    section = None
    for line in (ROOT / "rules" / "domains.txt").read_text().splitlines():
        line = line.strip()
        if not line or line[0] == "#":
            continue
        if line[0] == "[":
            section = line
        else:
            hosts[section] += 1
    return {
        "total": len(rules),
        "host_any": hosts["[block]"],
        "host_3p": hosts["[block-third-party]"],
        "urls": len(blocks) - sum(hosts.values()),
        "cosmetic": len(cosmetic),
        "selectors": sum(len(r["action"]["selector"].split(", ")) for r in cosmetic),
        "kb": round(LIST.stat().st_size / 1000),
    }


def banner(st):
    s = Svg(1200, 340)
    s.feather(1010, 170, scale=1.9, opacity=0.07)
    s.feather(120, 170)
    s.text(230, 172, "Feather", 64, FEATHER, "700")
    s.text(233, 214, "A lightweight ad blocker for Safari on macOS and iOS", 22, INK2)
    x = 232
    for label in (f"{st['total']} rules", f"{st['kb']} KB", "Zero page scripts outside youtube.com",
                  "macOS 13+ · iOS 16.4+"):
        w = tw(label, 17) + 40
        s.box(x, 250, w, 40, rx=20, opacity=0.08)
        s.text(x + w / 2, 275, label, 17, INK, anchor="middle")
        x += w + 12
    s.write("banner.svg")


def how_it_works(st):
    s = Svg(1200, 520)
    s.text(40, 52, "How Feather works", 26, INK, "700")
    s.text(40, 80, "Blocking happens inside Safari. The only script Feather runs is on youtube.com.", 16, INK2)

    # The rule list feeds the matcher.
    s.box(330, 104, 300, 36, rx=18, opacity=0.1)
    s.text(480, 127, f"{st['total']} rules · {st['kb']} KB · compiled once by Safari", 14, INK, anchor="middle")
    s.arrow([(480, 140), (480, 158)])

    # Lane 1: every site.
    s.text(40, 150, "EVERY SITE", 13, MUTED, "600", letter_spacing="1.5")
    s.box(40, 162, 230, 116)
    s.text(60, 196, "Page requests", 18, INK, "600")
    s.text(60, 220, "scripts, images, frames,", 14, INK2)
    s.text(60, 240, "beacons, media", 14, INK2)
    s.arrow([(270, 220), (326, 220)])

    s.box(330, 162, 300, 116)
    s.text(350, 196, "Safari's native matcher", 18, INK, "600")
    s.text(350, 220, "checks each URL against the", 14, INK2)
    s.text(350, 240, "compiled rules, in native code", 14, INK2)
    s.text(350, 264, "0 JavaScript from Feather", 13, MUTED)

    outs = [(190, "drop", "Ad and tracker requests dropped"),
            (250, "pass", "Everything else loads untouched"),
            (310, "pass", f"Leftover ad slots hidden with CSS ({st['selectors']} selectors)")]
    for i, (cy, kind, label) in enumerate(outs):
        s.arrow([(630, 220), (660, 220), (660, cy), (696, cy)])
        s.box(700, cy - 24, 460, 48)
        s.mark(722, cy, kind)
        s.text(742, cy + 5, label, 15, INK)

    # Lane 2: youtube.com only.
    s.text(40, 372, "YOUTUBE.COM ONLY", 13, MUTED, "600", letter_spacing="1.5")
    s.box(40, 384, 230, 116)
    s.text(60, 418, "YouTube player", 18, INK, "600")
    s.text(60, 442, "flags an ad on its own element", 14, INK2)
    s.text(60, 462, "with the class ad-showing", 14, INK2)
    s.arrow([(270, 442), (326, 442)])

    s.box(330, 384, 300, 116)
    s.text(350, 418, "Feather Skipper · 2 KB", 18, INK, "600")
    s.text(350, 442, "mutes, seeks to the end,", 14, INK2)
    s.text(350, 462, "presses Skip", 14, INK2)
    s.text(350, 486, "idle cost: one check per second", 13, MUTED)
    s.arrow([(630, 442), (696, 442)])
    s.box(700, 418, 460, 48)
    s.mark(722, 442, "pass")
    s.text(742, 447, "Ad over in under a second, sound restored", 15, INK)
    s.write("how-it-works.svg")


def rules_figure(st):
    s = Svg(1200, 320)
    s.text(40, 52, "What is in the list", 26, INK, "700")
    s.text(40, 80, f"{st['total']} rules in {st['kb']} KB. Hosts are most of it; the few cosmetic rules "
                   f"carry {st['selectors']} selectors between them.", 16, INK2)

    parts = [("Host blocks, any load", st["host_any"]),
             ("Host blocks, third-party only", st["host_3p"]),
             ("URL patterns", st["urls"]),
             ("Cosmetic rules", st["cosmetic"])]
    total = sum(v for _, v in parts)
    x, y, width, h, gap = 40, 106, 1120, 28, 2
    usable = width - gap * (len(parts) - 1)
    for i, (name, value) in enumerate(parts):
        w = usable * value / total
        s.parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="4" fill="{SERIES[i]}"/>')
        share = f"{round(100 * value / total)}%"
        if tw(share, 14) + 16 <= w:
            s.text(x + 10, y + 19, share, 14, LABEL_ON[i], "600")
        x += w + gap

    lx = 40
    for i, (name, _) in enumerate(parts):
        s.parts.append(f'<rect x="{lx}" y="{156}" width="12" height="12" rx="3" fill="{SERIES[i]}"/>')
        s.text(lx + 20, 167, name, 15, INK2)
        lx += 20 + tw(name, 15) + 36

    tiles = [(str(st["total"]), "rules in total"),
             (str(st["host_any"] + st["host_3p"]), "hosts blocked, subdomains included"),
             (str(st["selectors"]), f"CSS selectors in {st['cosmetic']} cosmetic rules"),
             (f"{st['kb']} KB", "on disk, compiled once by Safari")]
    tx, tw_, th, tgap = 40, 270, 90, 13
    for value, label in tiles:
        s.box(tx, 200, tw_, th)
        s.text(tx + 20, 244, value, 28, INK, "600")
        s.text(tx + 20, 270, label, 13, INK2)
        tx += tw_ + tgap
    s.write("rules.svg")


COVERAGE = [
    ("Video", [("YouTube", "ok"), ("YouTube Music", "ok"), ("Twitch", "part"), ("Hulu", "part"),
               ("Peacock", "part"), ("Paramount+", "part"), ("Pluto TV", "part"), ("Tubi", "part"),
               ("Crunchyroll", "part"), ("Netflix", "no"), ("Disney+", "no"), ("Max", "no"),
               ("Prime Video", "no")]),
    ("Music", [("Spotify web", "ok"), ("SoundCloud", "part"), ("Pandora", "part"),
               ("iHeart", "part"), ("TuneIn", "part")]),
    ("Search", [("Google", "ok"), ("Bing", "ok"), ("DuckDuckGo", "ok"), ("Yahoo", "ok"), ("Amazon", "ok")]),
    ("Social", [("Reddit", "ok"), ("LinkedIn", "ok"), ("X", "ok"), ("Facebook", "part"),
                ("Instagram", "part"), ("TikTok", "part"), ("Pinterest", "part")]),
    ("Forums", [("Discourse", "ok"), ("vBulletin", "ok"), ("XenForo", "ok"), ("Stack Exchange", "ok"),
                ("Fandom", "ok"), ("Quora", "part")]),
]
LEGEND = [("ok", "Ads blocked or hidden"),
          ("part", "Partly: ad calls and trackers blocked, stream-stitched ads remain"),
          ("no", "Not possible for any Safari extension")]


def coverage():
    # Lay out first to know the height.
    left, right, row_h, group_gap = 170, 1160, 46, 16
    y = 150
    placed = []
    for group, items in COVERAGE:
        x, first_y = left, y
        for label, kind in items:
            w = 16 + 18 + 10 + tw(label, 15) + 16
            if x + w > right:
                x, y = left, y + row_h
            placed.append((x, y, label, kind))
            x += w + 10
        placed.append((40, first_y, group, "group"))
        y += row_h + group_gap

    s = Svg(1200, y + 10)
    s.text(40, 52, "Where it works", 26, INK, "700")
    s.text(40, 80, "Network blocking and ad-slot hiding by platform. DRM streams with server-stitched ads "
                   "are out of reach for every Safari extension.", 16, INK2)
    lx = 40
    for kind, label in LEGEND:
        s.mark(lx + 9, 112, kind)
        s.text(lx + 26, 117, label, 14, INK2)
        lx += 26 + tw(label, 14) + 28
    for x, y, label, kind in placed:
        if kind == "group":
            s.text(x, y + 23, label.upper(), 13, MUTED, "600", letter_spacing="1.5")
        else:
            s.chip(x, y, label, kind)
    s.write("coverage.svg")


def main():
    DOCS.mkdir(exist_ok=True)
    st = stats()
    banner(st)
    how_it_works(st)
    rules_figure(st)
    coverage()


if __name__ == "__main__":
    main()
