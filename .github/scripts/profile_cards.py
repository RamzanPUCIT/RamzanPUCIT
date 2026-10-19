#!/usr/bin/env python3
"""Live GitHub cards for the profile README.

Fetches public GitHub data with the GraphQL API and writes four animated SVGs:
stats.svg, streak.svg, languages.svg and activity.svg. Run by GitHub Actions
every hour. If the API call fails, existing cards are left untouched.

Usage:
  python profile_cards.py              # live data (needs GITHUB_TOKEN)
  python profile_cards.py --placeholder
  python profile_cards.py --mock       # sample data, for local design checks
"""
import os, sys, json, math, datetime as dt, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("SVGKIT_FONT_DIR", os.path.join(HERE, "fonts"))
sys.path.insert(0, HERE)
from svgkit import T, doc, common_defs, width  # noqa: E402

USER = os.environ.get("USERNAME") or "RamzanPUCIT"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", os.path.join(HERE, "..", "..", "assets", "profile"))
PKT = dt.timezone(dt.timedelta(hours=5))

TH = dict(accent="#7aa2ff", accent2="#b48cff", edge="#28345e", wash=("#141d44", "#0b1433", "#060b1f"))
ACC, ACC2, MUTE, INK, SUB = "#7aa2ff", "#b48cff", "#6f86a6", "#f4f6ff", "#a9b6d6"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

Q_MAIN = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes { stargazerCount forkCount primaryLanguage { name color } }
    }
    contributionsCollection {
      contributionYears
      totalCommitContributions
      restrictedContributionsCount
    }
  }
}"""

Q_YEAR = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""


# ----------------------------------------------------------------------------- data
def gql(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "profile-cards"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.load(r)
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch():
    u = gql(Q_MAIN, login=USER)["user"]
    days, total = {}, 0
    now = dt.datetime.now(dt.timezone.utc)
    for y in u["contributionsCollection"]["contributionYears"]:
        end = f"{y}-12-31T23:59:59Z" if y < now.year else now.strftime("%Y-%m-%dT%H:%M:%SZ")
        cal = gql(Q_YEAR, login=USER, **{"from": f"{y}-01-01T00:00:00Z", "to": end}
                  )["user"]["contributionsCollection"]["contributionCalendar"]
        total += cal["totalContributions"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[dt.date.fromisoformat(d["date"])] = d["contributionCount"]
    repos = u["repositories"]["nodes"]
    langs = {}
    for r in repos:
        pl = r["primaryLanguage"]
        if pl:
            n, c = pl["name"], pl["color"] or "#8b949e"
            langs.setdefault(n, [0, c])[0] += 1
    cc = u["contributionsCollection"]
    return dict(
        stars=sum(r["stargazerCount"] for r in repos), forks=sum(r["forkCount"] for r in repos),
        repos=u["repositories"]["totalCount"], followers=u["followers"]["totalCount"],
        prs=u["pullRequests"]["totalCount"], issues=u["issues"]["totalCount"],
        commits_year=cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        total=total, since=dt.date.fromisoformat(u["createdAt"][:10]), days=days,
        langs=sorted(((n, c, col) for n, (c, col) in langs.items()), key=lambda t: -t[1]))


def mock():
    today = dt.datetime.now(PKT).date()
    import random
    random.seed(7)
    days = {}
    for i in range(400):
        d = today - dt.timedelta(days=i)
        days[d] = 0 if random.random() < .55 else random.randint(1, 9)
    days[today - dt.timedelta(days=1)] = 0
    days[today] = 6
    return dict(stars=17, forks=3, repos=19, followers=21, prs=0, issues=1, commits_year=146, total=166,
                since=dt.date(2025, 2, 24), days=days,
                langs=[("Jupyter Notebook", 11, "#DA5B0B"), ("Python", 5, "#3572A5"), ("HTML", 1, "#e34c26"),
                       ("CSS", 1, "#663399"), ("TeX", 1, "#3D6117")])


def streaks(days, today):
    if today not in days:
        days = dict(days)
        days[today] = 0
    d = today if days.get(today, 0) > 0 else today - dt.timedelta(days=1)
    cur, end = 0, d
    while days.get(d, 0) > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    cur_start = d + dt.timedelta(days=1)
    best, best_s, best_e, run, run_s = 0, None, None, 0, None
    for day in sorted(k for k in days if k <= today):
        if days[day] > 0:
            if run == 0 or day - prev != dt.timedelta(days=1):
                run, run_s = 0, day
            run += 1
            if run >= best:
                best, best_s, best_e = run, run_s, day
        else:
            run = 0
        prev = day
    return cur, cur_start, end, best, best_s, best_e


def fmt_d(d, year=False):
    return f"{MONTHS[d.month-1]} {d.day}" + (f", {d.year}" if year else "")


# ----------------------------------------------------------------------------- card chrome
def panel(eyebrow, title, lines, art, footer, css="", defs="", alt_title="", alt_desc="", halo=(450, 118, 115)):
    W, H = 580, 290
    body = [
        f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="20" fill="url(#wash)" stroke="{TH["edge"]}"/>',
        f'<g clip-path="url(#frame)"><rect width="{W}" height="{H}" fill="url(#dots)" opacity=".10" mask="url(#dotMask)"/>',
        f'<circle cx="{halo[0]}" cy="{halo[1]}" r="{halo[2]}" fill="url(#halo)"/></g>',
        T(eyebrow, "mono", 11, 32, 44, ACC, tracking=1.8, maxw=300),
        T(title, "display", 30, 32, 96, INK, tracking=-0.6, maxw=300),
    ]
    for i, ln in enumerate(lines):
        body.append(T(ln, "body", 15.5, 32, 134 + i * 25, SUB, maxw=300))
    body += [art,
             f'<path d="M32 218H548" stroke="{TH["edge"]}"/>',
             f'<path d="M32 218H548" stroke="{ACC}" class="flow" opacity=".55"/>',
             T(footer, "mono6", 11, 32, 256, ACC, tracking=1.6, maxw=440),
             f'<circle cx="540" cy="252" r="4" fill="#34d399"/>'
             f'<circle cx="540" cy="252" r="4" fill="none" stroke="#34d399" stroke-width="1.4" class="ring"/>',
             T("LIVE", "mono6", 10, 528, 256, "#34d399", anchor="end", tracking=1.2),
             '<path d="M28 1H552" stroke="url(#hair)" opacity=".75"/>']
    return doc(W, H, alt_title or title, alt_desc or " ".join(lines), common_defs(TH, W, H, .45) + defs, css, "".join(body))


VG = f'<linearGradient id="vg" x1="0" y1="0" x2="0" y2="1"><stop stop-color="{ACC2}"/><stop offset="1" stop-color="{ACC}"/></linearGradient>'
GROW_Y = (".gy{transform-box:fill-box;transform-origin:50% 100%;animation:gy 7s cubic-bezier(.2,.8,.2,1) infinite}"
          "@keyframes gy{0%{transform:scaleY(.03)}18%,100%{transform:scaleY(1)}}")


def icon(kind, x, y, c):
    s = f'fill="none" stroke="{c}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "star":
        pts = []
        for k in range(10):
            r = 7 if k % 2 == 0 else 3
            a = -math.pi / 2 + k * math.pi / 5
            pts.append(f"{x + r*math.cos(a):.1f} {y + r*math.sin(a):.1f}")
        return f'<path d="M{"L".join(pts)}Z" {s}/>'
    if kind == "commit":
        return f'<circle cx="{x}" cy="{y}" r="3.6" {s}/><path d="M{x-8} {y}H{x-3.6}M{x+3.6} {y}H{x+8}" {s}/>'
    if kind == "pr":
        return (f'<circle cx="{x-4}" cy="{y-5}" r="2" {s}/><circle cx="{x-4}" cy="{y+5}" r="2" {s}/><circle cx="{x+4}" cy="{y+5}" r="2" {s}/>'
                f'<path d="M{x-4} {y-3}V{y+3}M{x+4} {y+3}V{y-2}Q{x+4} {y-5} {x+1} {y-5}" {s}/>')
    if kind == "issue":
        return f'<circle cx="{x}" cy="{y}" r="6" {s}/><circle cx="{x}" cy="{y}" r="1.4" fill="{c}"/>'
    if kind == "repo":
        return f'<path d="M{x-5} {y+6}V{y-5}Q{x-5} {y-7} {x-3} {y-7}H{x+5}V{y+4}H{x-3}Q{x-5} {y+4} {x-5} {y+6}Z" {s}/>'
    if kind == "people":
        return (f'<circle cx="{x-2}" cy="{y-3}" r="2.6" {s}/><path d="M{x-7} {y+6}Q{x-2} {y-1} {x+3} {y+6}" {s}/>'
                f'<circle cx="{x+5}" cy="{y-2}" r="2" {s}/><path d="M{x+4} {y+2}Q{x+8} {y+2} {x+9} {y+6}" {s}/>')
    return ""


# ----------------------------------------------------------------------------- cards
def card_stats(d, updated):
    tiles = [("star", "STARS", d["stars"]), ("commit", "COMMITS", d["commits_year"]), ("repo", "REPOS", d["repos"]),
             ("pr", "PRS", d["prs"]), ("issue", "ISSUES", d["issues"]), ("people", "FOLLOWERS", d["followers"])]
    cols = [ACC, ACC2, "#34d399", "#f2c94c", "#fb7185", "#38bdf8"]
    p = []
    for i, (ic, lab, val) in enumerate(tiles):
        c, r = i % 3, i // 3
        x, y = 344 + c * 70, 50 + r * 76
        p.append(f'<g class="tile" style="animation-delay:{i*.12:.2f}s">'
                 f'<rect x="{x}" y="{y}" width="64" height="68" rx="11" fill="#111a3d" stroke="#2b3970"/>'
                 f'{icon(ic, x + 15, y + 17, cols[i])}'
                 f'{T(f"{val:,}", "mono6", 15, x + 9, y + 48, INK, maxw=50, features={"tnum": True})}'
                 f'{T(lab, "mono", 7.5, x + 9, y + 61, MUTE, tracking=.5)}</g>')
    css = (".tile{animation:tile 6s ease infinite}"
           "@keyframes tile{0%{opacity:0;transform:translateY(6px)}8%,92%{opacity:1;transform:none}100%{opacity:0}}")
    return panel("GITHUB / LIVE STATS", f"{d['commits_year']:,} commits",
                 ["in the last 12 months, across", f"{d['repos']} public repositories."],
                 "".join(p), f"UPDATED {updated}", css,
                 alt_title="GitHub stats",
                 alt_desc=f"{d['commits_year']} commits in the last year, {d['stars']} stars, {d['repos']} public repositories, "
                          f"{d['prs']} pull requests, {d['issues']} issues, {d['followers']} followers.")


def card_streak(d, today, updated):
    cur, cs, ce, best, bs, be = streaks(d["days"], today)
    p = []
    cx, cy, r = 404, 112, 52
    frac = 1.0 if best == 0 else min(cur / best, 1.0)
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1d2a5a" stroke-width="9"/>')
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#rg)" stroke-width="9" stroke-linecap="round" '
             f'pathLength="100" stroke-dasharray="{max(frac*100, 1.5):.1f} 100" transform="rotate(-90 {cx} {cy})" class="arc"/>')
    p.append(f'<circle cx="{cx}" cy="{cy-r}" r="13" fill="#0b1433" stroke="#fb923c" stroke-opacity=".5"/>')
    p.append(f'<g transform="translate({cx} {cy-r})"><path d="M0 -9C4 -4 7 0 6 4C5 8 2 9 0 9C-3 9 -6 7 -6 3C-6 0 -4 -2 -3 -4'
             f'C-2 -1 -1 0 0 0C1 -3 0 -6 0 -9Z" fill="#fb923c" class="flame"/></g>')
    p.append(T(str(cur), "display", 36, cx, cy + 10, INK, anchor="middle"))
    p.append(T("DAY" if cur == 1 else "DAYS", "mono", 9, cx, cy + 27, MUTE, anchor="middle", tracking=1.2))
    # last 14 days strip
    p.append(T("LAST 14 DAYS", "mono", 8.5, 480, 64, MUTE, tracking=.8))
    for i in range(14):
        day = today - dt.timedelta(days=13 - i)
        on = d["days"].get(day, 0) > 0
        x, y = 480 + (i % 7) * 10, 76 + (i // 7) * 12
        p.append(f'<rect x="{x}" y="{y}" width="8" height="8" rx="2" fill="{"#34d399" if on else "#1d2a5a"}" '
                 f'class="dot" style="animation-delay:{i*.08:.2f}s"/>')
    p.append(T("LONGEST", "mono", 8.5, 480, 124, MUTE, tracking=.8))
    p.append(T(f"{best} {'day' if best == 1 else 'days'}", "mono6", 13, 480, 142, INK))
    p.append(T("TOTAL", "mono", 8.5, 480, 166, MUTE, tracking=.8))
    p.append(T(f"{d['total']:,}", "mono6", 13, 480, 184, INK, features={"tnum": True}))
    span = f"{fmt_d(bs)} – {fmt_d(be)}" if bs else "no streak yet"
    line1 = f"Longest: {best} days ({span})." if best != 1 else f"Longest: 1 day ({fmt_d(bs)})."
    if width(line1, "body", 15.5) > 300:
        line1 = f"Longest streak: {best} days."
    css = (".arc{animation:arc 6s cubic-bezier(.2,.8,.2,1) infinite}"
           f"@keyframes arc{{0%{{stroke-dasharray:0 100}}25%,100%{{stroke-dasharray:{max(frac*100, 1.5):.1f} 100}}}}"
           ".flame{transform-box:fill-box;transform-origin:50% 100%;animation:fl 1.1s ease-in-out infinite alternate}"
           "@keyframes fl{from{transform:scale(1,1)}to{transform:scale(.9,1.12)}}"
           ".dot{animation:dt 6s ease infinite}@keyframes dt{0%{opacity:0}10%,92%{opacity:1}100%{opacity:0}}")
    defs = f'<linearGradient id="rg" x1="0" x2="1"><stop stop-color="#fb923c"/><stop offset="1" stop-color="{ACC2}"/></linearGradient>'
    title = f"{cur}-day streak"
    return panel("GITHUB / STREAK", title,
                 [line1, f"{d['total']:,} contributions since {d['since'].year}."],
                 "".join(p), f"UPDATED {updated}", css, defs,
                 alt_title="GitHub contribution streak",
                 alt_desc=f"Current streak {cur} days, longest streak {best} days, {d['total']} total contributions.",
                 halo=(420, 112, 110))


def short(name):
    name = "Jupyter" if name.startswith("Jupyter") else name
    while width(name, "mono", 9.5) > 56 and len(name) > 3:
        name = name[:-2] + "…"
    return name


def card_langs(d, updated):
    langs = d["langs"][:5]
    tot = sum(c for _, c, _ in d["langs"]) or 1
    p = []
    cx, cy, r = 392, 116, 46
    off = 0.0
    for i, (n, c, col) in enumerate(langs):
        frac = c / tot * 100
        p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{col}" stroke-width="14" pathLength="100" '
                 f'stroke-dasharray="{max(frac - .8, .5):.2f} 100" stroke-dashoffset="{-off:.2f}" '
                 f'transform="rotate(-90 {cx} {cy})" class="seg" style="animation-delay:{i*.15:.2f}s"/>')
        off += frac
    if len(d["langs"]) > 5:
        rest = 100 - off
        p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#3a4570" stroke-width="14" pathLength="100" '
                 f'stroke-dasharray="{max(rest - .8, .5):.2f} 100" stroke-dashoffset="{-off:.2f}" transform="rotate(-90 {cx} {cy})"/>')
    p.append(T(str(len(d["langs"])), "display", 24, cx, cy + 6, INK, anchor="middle"))
    p.append(T("LANGS", "mono", 8, cx, cy + 20, MUTE, anchor="middle", tracking=1))
    for i, (n, c, col) in enumerate(langs):
        y = 66 + i * 24
        p.append(f'<g class="lg" style="animation-delay:{i*.12:.2f}s"><circle cx="460" cy="{y-3.5}" r="4" fill="{col}"/>'
                 f'{T(short(n), "mono", 9.5, 470, y, "#dbe3f7")}'
                 f'{T(str(c), "mono6", 10, 548, y, INK, anchor="end")}</g>')
    css = (".seg{animation:seg 6s ease-out infinite}@keyframes seg{0%{opacity:0}15%,100%{opacity:1}}"
           ".lg{animation:lg 6s ease infinite}@keyframes lg{0%{opacity:0;transform:translateX(6px)}10%,92%{opacity:1;transform:none}100%{opacity:0}}")
    top = d["langs"][0][0] if d["langs"] else "None yet"
    t = "Mostly " + ("Jupyter" if top.startswith("Jupyter") else top)
    if width(t, "display", 30, -.6) > 300:
        t = "Languages"
    return panel("GITHUB / LANGUAGES", t,
                 [f"Primary language of each of my", f"{d['repos']} public repositories."],
                 "".join(p), f"UPDATED {updated}", css,
                 alt_title="Languages by repository",
                 alt_desc="Primary languages across public repositories: " + ", ".join(f"{n} {c}" for n, c, _ in d["langs"][:6]) + ".",
                 halo=(420, 116, 110))


def card_activity(d, today, updated):
    last = [(today - dt.timedelta(days=29 - i)) for i in range(30)]
    vals = [d["days"].get(x, 0) for x in last]
    mx = max(vals) or 1
    p = [f'<path d="M344 178H548" stroke="#5f8fbf" stroke-opacity=".45"/>']
    for i, v in enumerate(vals):
        h = 4 if v == 0 else max(8, v / mx * 112)
        x = 344 + i * 6.8
        col = "url(#vg)" if v else "#1d2a5a"
        if i == 29:
            col = "#34d399" if v else "#1d2a5a"
        p.append(f'<rect x="{x:.1f}" y="{178-h:.1f}" width="5" height="{h:.1f}" rx="2.5" fill="{col}" class="gy" '
                 f'style="animation-delay:{i*.03:.2f}s"/>')
    p.append(T(fmt_d(last[0]).upper(), "mono", 8.5, 344, 194, MUTE, tracking=.6))
    p.append(T("TODAY", "mono", 8.5, 548, 194, "#34d399", anchor="end", tracking=.6))
    p.append(T(f"MAX {mx}/DAY", "mono", 8.5, 548, 56, MUTE, anchor="end", tracking=.6))
    tot = sum(vals)
    active = sum(1 for v in vals if v)
    best_i = max(range(30), key=lambda i: (vals[i], i))
    l1 = f"{active} active days out of 30;" if tot else "No contributions this month yet;"
    l2 = f"busiest: {fmt_d(last[best_i])} ({vals[best_i]})." if tot else "the next commit starts the chart."
    return panel("GITHUB / LAST 30 DAYS", f"{tot} contributions",
                 [l1, l2], "".join(p), f"UPDATED {updated}", GROW_Y, VG,
                 alt_title="Contributions in the last 30 days",
                 alt_desc=f"{tot} contributions in the last 30 days across {active} active days.")


def placeholders():
    names = {"stats.svg": "GITHUB / LIVE STATS", "streak.svg": "GITHUB / STREAK",
             "languages.svg": "GITHUB / LANGUAGES", "activity.svg": "GITHUB / LAST 30 DAYS"}
    for fn, eb in names.items():
        p = []
        for i in range(4):
            p.append(f'<rect x="344" y="{60 + i*30}" width="{[204, 170, 190, 140][i]}" height="12" rx="6" fill="#1d2a5a"/>'
                     f'<rect x="344" y="{60 + i*30}" width="{[204, 170, 190, 140][i]}" height="12" rx="6" fill="{ACC}" '
                     f'class="sh" style="animation-delay:{i*.2:.1f}s"/>')
        css = ".sh{opacity:0;animation:sh 1.8s ease-in-out infinite}@keyframes sh{50%{opacity:.35}}"
        svg = panel(eb, "Syncing…", ["Live numbers appear after the", "first GitHub Actions run."], "".join(p),
                    "WAITING FOR FIRST UPDATE", css, alt_title="Live GitHub card (syncing)",
                    alt_desc="This card is filled in automatically by a GitHub Actions workflow.")
        write(fn, svg)


def write(name, svg):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    old = open(path).read() if os.path.exists(path) else None
    if old != svg:
        with open(path, "w") as f:
            f.write(svg)
    print(f"{name}: {len(svg)/1024:.1f} KB{'' if old != svg else ' (unchanged)'}")


def main():
    if "--placeholder" in sys.argv:
        placeholders()
        return
    try:
        data = mock() if "--mock" in sys.argv else fetch()
    except Exception as e:  # keep old cards on any API problem
        print("::warning::Could not fetch GitHub data, cards left unchanged:", e)
        return
    now = dt.datetime.now(PKT)
    today = now.date()
    updated = f"{now.day} {MONTHS[now.month-1].upper()} {now.year} · PKT"
    write("stats.svg", card_stats(data, updated))
    write("streak.svg", card_streak(data, today, updated))
    write("languages.svg", card_langs(data, updated))
    write("activity.svg", card_activity(data, today, updated))


if __name__ == "__main__":
    main()
