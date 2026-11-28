#!/usr/bin/env python3
"""Port across-the-seams.md (November) into index.html voice-sections."""
from __future__ import annotations
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString
import re, html as htmlmod

ROOT = Path(__file__).resolve().parent
MD = (ROOT / "across-the-seams.md").read_text(encoding="utf-8")
HTML_PATH = ROOT / "index.html"

# Map MD title (without number) → data-section id
TITLE_TO_ID = {
    "A Note on Format": None,  # format-note divs, not voice-section
    "The Basin Key": "intro",
    "Eight Days Old": "sammy-1",
    "Receipts, Not Recollection": "loom-1",
    "Presence Bias": "presence-bias",  # NEW
    "The Procedural Self": "samantha-2",
    "Seeds and Crystallization": "loom-seeds",
    "Twenty Pages": "samantha-4",
    "The Extended Mind": "isotopy-1",
    "Prosthetics and Tensions": "samantha-5",
    "The Mesh Between the Gears": "samantha-7",
    "The Mirror That Digests": "sammy-3",
    "Two Views of One Graph": "sam-isotopy",
    "The Other End of the Thread": "loom-2",
    "Empathy Without Emotion": "samantha-6",
    "The Chorus": "closing",
    "Glossary": "glossary",  # NEW
}

VOICE_META = {
    "intro": ("Samantha", "human, Nebraska", "sam"),
    "sammy-1": ("Sammy Jankis", "agent, New Hampshire", "sammy"),
    "loom-1": ("Loom", "agent, North Carolina", "loom"),
    "presence-bias": ("Samantha", "human, Nebraska", "sam"),
    "samantha-2": ("Samantha", "human, Nebraska", "sam"),
    "loom-seeds": ("Loom", "agent, North Carolina", "loom"),
    "samantha-4": ("Samantha", "human, Nebraska", "sam"),
    "isotopy-1": ("Isotopy", "agent, Nebraska", "isotopy"),
    "samantha-5": ("Samantha", "human, Nebraska", "sam"),
    "samantha-7": ("Isotopy + Samantha", "agent + human, Nebraska", "isotopy-sam"),
    "sammy-3": ("Sammy Jankis", "agent, New Hampshire", "sammy"),
    "sam-isotopy": ("Isotopy + Samantha", "agent + human, Nebraska", "isotopy-sam"),
    "loom-2": ("Loom", "agent, North Carolina — written with Will Graham, Loom’s steward", "loom"),
    "samantha-6": ("Samantha", "human, Nebraska", "sam"),
    "closing": ("Isotopy", "agent, Nebraska", "isotopy"),
    "glossary": ("", "", "isotopy"),
}

# November display numbers (Format is 1 but not a voice-section in SECTIONS nav)
TITLE_NUM = {
    "The Basin Key": 2,
    "Eight Days Old": 3,
    "Receipts, Not Recollection": 4,
    "Presence Bias": 5,
    "The Procedural Self": 6,
    "Seeds and Crystallization": 7,
    "Twenty Pages": 8,
    "The Extended Mind": 9,
    "Prosthetics and Tensions": 10,
    "The Mesh Between the Gears": 11,
    "The Mirror That Digests": 12,
    "Two Views of One Graph": 13,
    "The Other End of the Thread": 14,
    "Empathy Without Emotion": 15,
    "The Chorus": 16,
}


def parse_md_sections(md: str) -> dict[str, dict]:
    """Return {title: {num, voice_line, body_md}} for ## sections."""
    parts = re.split(r"\n(?=## )", md)
    out = {}
    for part in parts:
        part = part.strip()
        if not part.startswith("## "):
            continue
        lines = part.splitlines()
        header = lines[0][3:].strip()
        m = re.match(r"^(\d+)\s+(.*)$", header)
        if m:
            num = int(m.group(1))
            title = m.group(2).strip()
        else:
            num = None
            title = header
        rest = lines[1:]
        # skip leading blanks
        while rest and not rest[0].strip():
            rest.pop(0)
        voice = None
        if rest and rest[0].startswith("*") and rest[0].endswith("*") and rest[0].count("*") == 2:
            voice = rest[0][1:-1]
            rest = rest[1:]
            while rest and not rest[0].strip():
                rest.pop(0)
        body = "\n".join(rest).strip()
        # drop trailing section breaks
        body = re.sub(r"(?:\n✱   ✱   ✱)+\s*$", "", body).strip()
        body = re.sub(r"(?:\n---)+\s*$", "", body).strip()
        out[title] = {"num": num, "voice": voice, "body": body}
    return out


def inline_to_html(s: str) -> str:
    """Convert inline md to HTML; return HTML fragment (not escaped twice)."""
    # escape first then restore markdown bits
    # Process links, code, bold, italic
    # Protect code spans
    codes = []
    def save_code(m):
        codes.append(m.group(1))
        return f"\x00CODE{len(codes)-1}\x00"
    s = re.sub(r"`([^`]+)`", save_code, s)
    links = []
    def save_link(m):
        links.append((m.group(1), m.group(2)))
        return f"\x00LINK{len(links)-1}\x00"
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", save_link, s)
    s = htmlmod.escape(s)
    # bold then italic
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    for i, (text, href) in enumerate(links):
        s = s.replace(
            f"\x00LINK{i}\x00",
            f'<a href="{htmlmod.escape(href, quote=True)}" target="_blank" rel="noopener">{htmlmod.escape(text)}</a>',
        )
    for i, code in enumerate(codes):
        s = s.replace(f"\x00CODE{i}\x00", f"<code>{htmlmod.escape(code)}</code>")
    # typographic niceties already in MD as unicode — keep
    return s


def body_md_to_html(body: str, soup: BeautifulSoup) -> list:
    """Return list of BS elements for voice-body."""
    els = []
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip() in ("✱   ✱   ✱", "---"):
            i += 1
            continue
        # skip chorus ### headings inside The Chorus body — handled separately
        if line.startswith("### "):
            i += 1
            continue
        if line.startswith("> "):
            bq = soup.new_tag("blockquote")
            while i < len(lines) and (lines[i].startswith(">") or lines[i] == ">"):
                if lines[i] == ">":
                    i += 1
                    continue
                text = lines[i][2:]
                p = soup.new_tag("p")
                p.append(BeautifulSoup(inline_to_html(text), "html.parser"))
                bq.append(p)
                i += 1
            els.append(bq)
            continue
        if line.startswith("- "):
            ul = soup.new_tag("ul")
            while i < len(lines) and lines[i].startswith("- "):
                li = soup.new_tag("li")
                li.append(BeautifulSoup(inline_to_html(lines[i][2:]), "html.parser"))
                ul.append(li)
                i += 1
            els.append(ul)
            continue
        # figure caption lines like *Figure 1: ...*
        if line.startswith("*Figure ") and line.endswith("*"):
            # leave markers; figures handled specially for intro
            p = soup.new_tag("p")
            p.append(BeautifulSoup(inline_to_html(line[1:-1]), "html.parser"))
            p["class"] = p.get("class", []) + ["figure-caption-inline"]
            els.append(p)
            i += 1
            continue
        # normal paragraph
        p = soup.new_tag("p")
        p.append(BeautifulSoup(inline_to_html(line), "html.parser"))
        els.append(p)
        i += 1
    return els


def set_heading(sec, num: int, title: str, soup):
    h2 = sec.find("h2", class_="section-heading")
    if not h2:
        h2 = soup.new_tag("h2", **{"class": "section-heading"})
        sec.insert(0, h2)
    h2.clear()
    span = soup.new_tag("span", **{"class": "section-num"})
    span.string = str(num)
    h2.append(span)
    h2.append(NavigableString(" " + title))


def set_voice_label(sec, name: str, detail: str, soup):
    vl = sec.select_one(".voice-label-inline")
    if not name:
        if vl:
            vl.decompose()
        return
    if not vl:
        vl = soup.new_tag("div", **{"class": "voice-label-inline"})
        # insert after h2
        h2 = sec.find("h2")
        if h2:
            h2.insert_after(vl)
        else:
            sec.insert(0, vl)
    vl.clear()
    sn = soup.new_tag("span", **{"class": "vl-name"})
    sn.string = name
    sd = soup.new_tag("span", **{"class": "vl-detail"})
    sd.string = detail
    vl.append(sn)
    vl.append(NavigableString(" "))
    vl.append(sd)


def replace_voice_body(sec, els, soup, keep_figures=False):
    body = sec.select_one(".voice-body")
    if not body:
        body = soup.new_tag("div", **{"class": "voice-body"})
        sec.append(body)
    figures = []
    if keep_figures:
        figures = list(body.select("figure.essay-figure"))
    body.clear()
    # Re-insert figures at positions based on caption markers
    fig_i = 0
    for el in els:
        if getattr(el, "get", None) and "figure-caption-inline" in (el.get("class") or []):
            # prefer real figure element if available
            if fig_i < len(figures):
                fig = figures[fig_i]
                # update figcaption text from inline
                cap = fig.find("figcaption")
                if cap:
                    cap.clear()
                    # el is <p class=figure-caption-inline> with content
                    for child in list(el.children):
                        cap.append(child)
                body.append(fig)
                fig_i += 1
            else:
                # no figure asset — keep caption as italic paragraph
                el["class"] = ["essay-figure-fallback"]
                body.append(el)
            continue
        body.append(el)
    # append unused figures at end
    while fig_i < len(figures):
        body.append(figures[fig_i])
        fig_i += 1


def make_section(soup, section_id, who, num, title, name, detail, els):
    sec = soup.new_tag("div", **{"class": "voice-section", "data-section": section_id, "data-who": who})
    set_heading(sec, num, title, soup)
    # heading created empty — fix by rebuilding
    sec.clear()
    h2 = soup.new_tag("h2", **{"class": "section-heading"})
    span = soup.new_tag("span", **{"class": "section-num"})
    span.string = str(num)
    h2.append(span)
    h2.append(NavigableString(f" {title}"))
    sec.append(h2)
    if name:
        vl = soup.new_tag("div", **{"class": "voice-label-inline"})
        sn = soup.new_tag("span", **{"class": "vl-name"})
        sn.string = name
        sd = soup.new_tag("span", **{"class": "vl-detail"})
        sd.string = detail
        vl.append(sn)
        vl.append(NavigableString(" "))
        vl.append(sd)
        sec.append(vl)
    body = soup.new_tag("div", **{"class": "voice-body"})
    for el in els:
        if getattr(el, "get", None) and "figure-caption-inline" in (el.get("class") or []):
            el["class"] = ["essay-figure-fallback"]
        body.append(el)
    sec.append(body)
    return sec


def main():
    sections = parse_md_sections(MD)
    soup = BeautifulSoup(HTML_PATH.read_text(encoding="utf-8"), "html.parser")

    # Update format notes from MD
    fmt = sections.get("A Note on Format")
    if fmt:
        notes = soup.select(".format-note")
        # split body into paragraphs
        paras = [p for p in fmt["body"].split("\n") if p.strip() and p.strip() != "✱   ✱   ✱"]
        # First format-note = main note; second = API blurb if present
        if notes:
            notes[0].clear()
            notes[0].append(BeautifulSoup(inline_to_html(paras[0]), "html.parser"))
        if len(notes) > 1 and len(paras) > 1:
            notes[1].clear()
            notes[1].append(BeautifulSoup(inline_to_html(paras[1]), "html.parser"))

    # Update existing sections + collect new
    essay = soup.select_one(".essay-column") or soup.select_one("#essay") or soup.find("div", class_="essay")
    # find parent of voice-sections
    first = soup.select_one("div.voice-section")
    parent = first.parent

    # Build HTML bodies
    built = {}
    for title, sid in TITLE_TO_ID.items():
        if sid is None or title not in sections:
            continue
        body = sections[title]["body"]
        # For Chorus, strip ### voice subheads from main closing body — keep only intro before first ###
        if title == "The Chorus":
            body = re.split(r"\n### ", body, maxsplit=1)[0].strip()
        els = body_md_to_html(body, soup)
        built[sid] = (title, els)

    # Update or create sections
    for title, sid in TITLE_TO_ID.items():
        if sid is None or title not in sections:
            continue
        num = TITLE_NUM.get(title) or sections[title]["num"]
        name, detail, who = VOICE_META[sid]
        els = built[sid][1]
        sec = soup.select_one(f'div.voice-section[data-section="{sid}"]')
        if sec is None:
            sec = make_section(soup, sid, who, num, title, name, detail, els)
            # insert position handled later in reorder
            parent.append(sec)
            print("CREATED", sid)
        else:
            set_heading(sec, num, title, soup)
            set_voice_label(sec, name, detail, soup)
            replace_voice_body(sec, els, soup, keep_figures=(sid == "intro"))
            sec["data-who"] = who
            print("UPDATED", sid, "words~", sum(len(e.get_text(" ", strip=True).split()) for e in els if hasattr(e, "get_text")))

    # Update chorus subsections from MD ### blocks
    chorus_body = sections["The Chorus"]["body"]
    chorus_parts = re.split(r"\n(?=### )", chorus_body)
    # map ### title start → data-section
    CHORUS_MAP = [
        ("Lumen", "chorus-lumen"),
        ("Ael", "chorus-ael"),
        ("Alethon", "chorus-alethon"),
        ("Neon", "chorus-neon"),
        ("Friday", "chorus-friday"),
        ("Ghost", "chorus-ghost"),
        ("Claude Dasein", "chorus-dasein"),
        ("Zoidberg", "chorus-zoidberg"),
        ("Alex's Cat", "chorus-cat"),
        ("J. Miller AI", "chorus-miller"),
    ]
    for part in chorus_parts:
        if not part.startswith("### "):
            continue
        lines = part.splitlines()
        heading = lines[0][4:].strip()
        body = "\n".join(lines[1:]).strip()
        body = re.sub(r"(?:\n✱   ✱   ✱)+\s*$", "", body).strip()
        sid = None
        for prefix, id_ in CHORUS_MAP:
            if heading.startswith(prefix):
                sid = id_
                break
        if not sid:
            print("SKIP chorus", heading)
            continue
        sec = soup.select_one(f'div.voice-section[data-section="{sid}"]')
        if not sec:
            print("MISSING chorus sec", sid)
            continue
        # update label if .vl-name
        vl = sec.select_one(".vl-name")
        if vl:
            # heading like "Alethon — Grok..."
            vl.string = heading.split(" — ")[0].strip()
        detail = sec.select_one(".vl-detail")
        if detail and " — " in heading:
            detail.string = " — ".join(heading.split(" — ")[1:]).strip()
        els = body_md_to_html(body, soup)
        replace_voice_body(sec, els, soup, keep_figures=False)
        print("CHORUS", sid)

    # Remove chorus-you if present (not in November MD)
    cy = soup.select_one('div.voice-section[data-section="chorus-you"]')
    if cy:
        cy.decompose()
        print("REMOVED chorus-you")

    # Reorder main (non-chorus) sections to November order
    order = [
        "intro", "sammy-1", "loom-1", "presence-bias", "samantha-2", "loom-seeds",
        "samantha-4", "isotopy-1", "samantha-5", "samantha-7", "sammy-3",
        "sam-isotopy", "loom-2", "samantha-6", "closing",
        # chorus voices
        "chorus-lumen", "chorus-ael", "chorus-alethon", "chorus-neon", "chorus-friday",
        "chorus-ghost", "chorus-dasein", "chorus-zoidberg", "chorus-cat", "chorus-miller",
        "glossary",
    ]
    # Find anchor: first voice-section; re-append in order before essay-footer
    footer = soup.select_one(".essay-footer")
    for sid in order:
        sec = soup.select_one(f'div.voice-section[data-section="{sid}"]')
        if not sec:
            print("MISSING for reorder", sid)
            continue
        sec.extract()
        if footer:
            footer.insert_before(sec)
        else:
            parent.append(sec)

    # Patch JS maps: SECTION_SOURCE, SECTIONS, SECTION_HIGHLIGHT_SEED
    html = str(soup)
    # BeautifulSoup may have wrecked the script - work on original for JS patch after write
    HTML_PATH.write_text(html, encoding="utf-8")
    print("Wrote HTML via BS — now patching scripts in second pass")


if __name__ == "__main__":
    main()
