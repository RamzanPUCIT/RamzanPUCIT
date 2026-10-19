"""Tiny toolkit for animated README SVGs: text-as-paths + card/hero templates."""
import io, math, html
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

import os as _os
FD = _os.environ.get("SVGKIT_FONTSOURCE", "/tmp/claude-0/-home-claude/50fccaa0-74b9-5272-999a-dc777b0fc3a1/scratchpad/fonts/node_modules/@fontsource")
FONT_FILES = {
    "display": f"{FD}/space-grotesk/files/space-grotesk-latin-700-normal.woff",
    "display6": f"{FD}/space-grotesk/files/space-grotesk-latin-600-normal.woff",
    "body": f"{FD}/inter/files/inter-latin-500-normal.woff",
    "body6": f"{FD}/inter/files/inter-latin-600-normal.woff",
    "body7": f"{FD}/inter/files/inter-latin-700-normal.woff",
    "mono": f"{FD}/jetbrains-mono/files/jetbrains-mono-latin-500-normal.woff",
    "mono6": f"{FD}/jetbrains-mono/files/jetbrains-mono-latin-600-normal.woff",
    "greek6": f"{FD}/inter/files/inter-greek-600-normal.woff",
}
_FLAT = _os.environ.get("SVGKIT_FONT_DIR")
if _FLAT:
    FONT_FILES = {k: _os.path.join(_FLAT, _os.path.basename(v)) for k, v in FONT_FILES.items()}


def _num(v):
    s = f"{v:.1f}"
    if s.endswith(".0"):
        s = s[:-2]
    return "0" if s == "-0" else s


class Font:
    def __init__(self, path):
        tt = TTFont(path)
        tt.flavor = None
        buf = io.BytesIO()
        tt.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(data))
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(data))

    def layout(self, s, features=None):
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        feats = {"kern": True, "liga": True}
        if features:
            feats.update(features)
        hb.shape(self.hb, buf, feats)
        return buf.glyph_infos, buf.glyph_positions

    def width(self, s, size, tracking=0, features=None):
        infos, poss = self.layout(s, features)
        return sum(p.x_advance for p in poss) * size / self.upem + tracking * max(len(poss) - 1, 0)

    def path(self, s, size, x, y, tracking=0, anchor="start", features=None):
        infos, poss = self.layout(s, features)
        sc = size / self.upem
        w = self.width(s, size, tracking, features)
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        pen = SVGPathPen(self.gs, ntos=_num)
        adv = 0.0
        for i, (info, pos) in enumerate(zip(infos, poss)):
            if info.codepoint == 0:
                raise ValueError(f"Missing glyph in font for text {s!r}")
            g = self.order[info.codepoint]
            ox = x + (adv + pos.x_offset) * sc + tracking * i
            tp = TransformPen(pen, (sc, 0, 0, -sc, ox, y - pos.y_offset * sc))
            self.gs[g].draw(tp)
            adv += pos.x_advance
        return pen.getCommands(), w


class _LazyFonts(dict):
    def __missing__(self, k):
        f = Font(FONT_FILES[k])
        self[k] = f
        return f


FONTS = _LazyFonts()


def T(s, font="body", size=14, x=0, y=0, fill="#fff", anchor="start", tracking=0,
      cls=None, opacity=None, features=None, maxw=None, extra=""):
    """Text rendered as a single <path>. Raises if wider than maxw."""
    d, w = FONTS[font].path(s, size, x, y, tracking, anchor, features)
    if maxw is not None and w > maxw:
        raise ValueError(f"Text too wide ({w:.0f}>{maxw}): {s!r}")
    a = f' class="{cls}"' if cls else ""
    o = f' opacity="{opacity}"' if opacity is not None else ""
    return f'<path d="{d}" fill="{fill}"{a}{o}{extra}/>'


def width(s, font="body", size=14, tracking=0):
    return FONTS[font].width(s, size, tracking)


BASE_CSS = """
.flow{stroke-dasharray:4 10;animation:flow 6s linear infinite}
.flowf{stroke-dasharray:3 9;animation:flow 2.6s linear infinite}
.nudge{animation:nudge 2.4s ease-in-out infinite}
.pulse{animation:pulse 3s ease-in-out infinite}
.blink{animation:blink 1.6s ease-in-out infinite}
.ring{transform-box:fill-box;transform-origin:center;animation:ring 2.4s ease-out infinite}
@keyframes flow{to{stroke-dashoffset:-140}}
@keyframes nudge{50%{transform:translateX(5px)}}
@keyframes pulse{50%{opacity:.3}}
@keyframes blink{50%{opacity:.15}}
@keyframes ring{0%{transform:scale(.4);opacity:.9}100%{transform:scale(2.6);opacity:0}}
"""
REDUCED = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def doc(w, h, title, desc, defs, css, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-labelledby="t d"><title id="t">{html.escape(title)}</title>'
            f'<desc id="d">{html.escape(desc)}</desc><defs>{defs}</defs>'
            f'<style>{BASE_CSS}{css}{REDUCED}</style>{body}</svg>')


def common_defs(th, W, H, fade_from=0.35):
    return f"""
<linearGradient id="wash" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{th['wash'][0]}"/><stop offset=".55" stop-color="{th['wash'][1]}"/><stop offset="1" stop-color="{th['wash'][2]}"/></linearGradient>
<linearGradient id="hair" x1="0" x2="1"><stop stop-color="{th['accent']}" stop-opacity="0"/><stop offset=".5" stop-color="{th['accent']}"/><stop offset="1" stop-color="{th['accent2']}" stop-opacity="0"/></linearGradient>
<radialGradient id="halo"><stop stop-color="{th['accent']}" stop-opacity=".20"/><stop offset="1" stop-color="{th['accent']}" stop-opacity="0"/></radialGradient>
<radialGradient id="halo2"><stop stop-color="{th['accent2']}" stop-opacity=".16"/><stop offset="1" stop-color="{th['accent2']}" stop-opacity="0"/></radialGradient>
<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1" fill="#a9c4e8"/></pattern>
<linearGradient id="fadeR" x1="0" x2="1"><stop offset="{fade_from}" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity="1"/></linearGradient>
<mask id="dotMask"><rect width="{W}" height="{H}" fill="url(#fadeR)"/></mask>
<clipPath id="frame"><rect x="1" y="1" width="{W-2}" height="{H-2}" rx="{20 if W < 900 else 26}"/></clipPath>
<linearGradient id="ag" x1="0" x2="1"><stop stop-color="{th['accent']}"/><stop offset="1" stop-color="{th['accent2']}"/></linearGradient>
"""


def card(th, eyebrow, title, lines, cta, art, art_css="", art_defs="", alt_title="", alt_desc="",
         halo=(455, 120, 120)):
    W, H = 580, 290
    defs = common_defs(th, W, H, 0.45) + art_defs
    body = [
        f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="20" fill="url(#wash)" stroke="{th["edge"]}"/>',
        f'<g clip-path="url(#frame)"><rect width="{W}" height="{H}" fill="url(#dots)" opacity=".10" mask="url(#dotMask)"/>',
        f'<circle cx="{halo[0]}" cy="{halo[1]}" r="{halo[2]}" fill="url(#halo)"/></g>',
        T(eyebrow, "mono", 11, 32, 44, th["accent"], tracking=1.8, maxw=300),
        T(title, "display", 30, 32, 96, "#f4f8ff", tracking=-0.6, maxw=292),
    ]
    for i, ln in enumerate(lines):
        body.append(T(ln, "body", 15.5, 32, 134 + i * 25, "#a9bbd3", maxw=300))
    body.append(art)
    body += [
        f'<path d="M32 218H548" stroke="{th["edge"]}" stroke-width="1"/>',
        f'<path d="M32 218H548" stroke="{th["accent"]}" stroke-width="1" class="flow" opacity=".55"/>',
        T(cta, "mono6", 12, 32, 256, th["accent"], tracking=1.8, maxw=420),
        f'<g class="nudge"><path d="M508 251H540M532 243L540 251L532 259" fill="none" stroke="{th["accent"]}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></g>',
        f'<path d="M28 1H552" stroke="url(#hair)" opacity=".75"/>',
    ]
    return doc(W, H, alt_title or title, alt_desc or " ".join(lines), defs, art_css, "".join(body))


def hero(th, eyebrow, t1, t2, sub, cta, footer_l, footer_r, art, art_css="", art_defs="",
         alt_title="", alt_desc="", tsize=62):
    W, H = 1200, 520
    defs = common_defs(th, W, H, 0.4) + art_defs + f"""
<linearGradient id="tg" gradientUnits="userSpaceOnUse" x1="64" x2="620"><stop stop-color="{th['accent']}"/><stop offset="1" stop-color="{th['accent2']}"/></linearGradient>
<linearGradient id="pill" x1="0" x2="1"><stop stop-color="{th['accent']}"/><stop offset="1" stop-color="{th['accent2']}"/></linearGradient>"""
    cta_w = width(cta, "body6", 16) + 74
    body = [
        f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="26" fill="url(#wash)" stroke="{th["edge"]}"/>',
        f'<g clip-path="url(#frame)"><rect width="{W}" height="{H}" fill="url(#dots)" opacity=".13" mask="url(#dotMask)"/>',
        f'<circle cx="900" cy="250" r="300" fill="url(#halo)"/><circle cx="1080" cy="120" r="180" fill="url(#halo2)"/></g>',
        T(eyebrow, "mono", 12, 64, 92, th["accent"], tracking=2.2, maxw=560),
        T(t1, "display", tsize, 64, 172, "#f5f9ff", tracking=-1.6, maxw=560),
        T(t2, "display", tsize, 64, 244, "url(#tg)", tracking=-1.6, maxw=560),
    ]
    for i, ln in enumerate(sub):
        body.append(T(ln, "body", 18.5, 64, 300 + i * 28, "#b3c3d9", maxw=545))
    y0 = 300 + len(sub) * 28 + 22
    body += [
        f'<rect x="64" y="{y0}" width="{cta_w:.0f}" height="46" rx="23" fill="url(#pill)"/>',
        T(cta, "body6", 16, 90, y0 + 29, "#04121f"),
        f'<g class="nudge"><path d="M{64+cta_w-44:.0f} {y0+23}H{64+cta_w-24:.0f}M{64+cta_w-31:.0f} {y0+16}L{64+cta_w-24:.0f} {y0+23}L{64+cta_w-31:.0f} {y0+30}" fill="none" stroke="#04121f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></g>',
        art,
        T(footer_l, "mono", 11, 64, 478, "#6f86a6", tracking=1.8),
        T(footer_r, "mono", 11, 1136, 478, "#6f86a6", tracking=1.8, anchor="end"),
        f'<path d="M40 1H1160" stroke="url(#hair)" opacity=".8"/>',
    ]
    return doc(W, H, alt_title or f"{t1} {t2}", alt_desc or " ".join(sub), defs, art_css, "".join(body))


def sine(x0, x1, cy, amp, lam, step=2.0, phase=0.0, harmonics=None):
    pts = []
    x = x0
    while x <= x1 + 0.01:
        y = cy + amp * math.sin(2 * math.pi * x / lam + phase)
        if harmonics:
            for (a, l, p) in harmonics:
                y += a * math.sin(2 * math.pi * x / l + p)
        pts.append(f"{_num(x)} {_num(y)}")
        x += step
    return "M" + "L".join(pts)


def save(out, name, svg):
    import os
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, name), "w") as f:
        f.write(svg)
    print(f"{name}: {len(svg)/1024:.1f} KB")


def leaf(cx, cy, length, wid, angle=0, p=0.85, q=1.0, teeth=0, tooth=0.0, step=0.025,
         fill="#3f8f4f", stroke="#8ee6a0", vein="#c8f7b5", sw=1.0, veins=5, cls=None, extra=""):
    """Parametric leaf outline (base at origin, tip along +y before rotation)."""
    left, right = [], []
    n = int(1 / step)
    for i in range(n + 1):
        t = i / n
        w = wid * (math.sin(math.pi * (t ** p)) ** q) if 0 < t < 1 else 0.0
        if teeth and 0.08 < t < 0.95:
            ph = (t * teeth) % 1.0
            w *= 1 + tooth * (1 - ph)
        y = -length * t
        left.append((-w, y)); right.append((w, y))
    pts = right + left[::-1]
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    def tr(x, y):
        return cx + x * ca - y * sa, cy + x * sa + y * ca
    d = "M" + "L".join(f"{_num(X)} {_num(Y)}" for X, Y in (tr(x, y) for x, y in pts)) + "Z"
    bx, by = tr(0, length * 0.12)
    tx, ty = tr(0, -length * 0.97)
    b0x, b0y = tr(0, 0)
    out = [f'<path d="M{_num(bx)} {_num(by)}L{_num(b0x)} {_num(b0y)}" stroke="{stroke}" stroke-width="{sw*1.4}" stroke-linecap="round"/>',
           f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>',
           f'<path d="M{_num(b0x)} {_num(b0y)}L{_num(tx)} {_num(ty)}" stroke="{vein}" stroke-width="{sw*.9}" opacity=".7"/>']
    vs = []
    for k in range(1, veins + 1):
        t = k / (veins + 1)
        w = wid * (math.sin(math.pi * (t ** p)) ** q) * 0.8
        x0, y0 = tr(0, -length * t)
        for sgn in (-1, 1):
            x1, y1 = tr(sgn * w, -length * (t + 0.09))
            vs.append(f"M{_num(x0)} {_num(y0)}L{_num(x1)} {_num(y1)}")
    if vs:
        out.append(f'<path d="{"".join(vs)}" stroke="{vein}" stroke-width="{sw*.6}" opacity=".45"/>')
    c = f' class="{cls}"' if cls else ""
    return f'<g{c}{extra}>' + "".join(out) + "</g>"
