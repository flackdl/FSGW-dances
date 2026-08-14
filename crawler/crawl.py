#!/usr/bin/env python3
"""Crawl FSGW "Dances Called" pages and produce data/dances.json.

Usage:
    .venv/bin/python crawler/crawl.py [--cache DIR] [--refresh] [--out data/dances.json]

The script:
  1. Fetches the index page and discovers every quarterly listing URL
     (1997 through the present), in four distinct formats:
       - modern HTML (2022+)
       - prior-year HTML (2007-2021)
       - plain text (1998-2006)
       - the 1997 "latter months" text file
  2. Parses each page into one record per individual dance.
  3. Writes a single normalized JSON document to --out.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# html5lib implements the HTML5 tree-construction algorithm and correctly
# handles the malformed/unclosed <tr> markup found on the source pages.
HTML_PARSER = "html5lib"

BASE_URL = "https://fsgw2.org/ecd/dancescalled/"
INDEX_URL = urljoin(BASE_URL, "d.called.html")

HEADERS = {"User-Agent": "FSGW-dances-crawler/1.0 (personal archival use)"}

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def fetch(url, cache_dir=None, refresh=False, timeout=60):
    """Return (text, ok). Uses on-disk cache unless refresh is True."""
    key = url.replace(BASE_URL, "").replace("/", "__") or "index.html"
    cache_path = os.path.join(cache_dir, key) if cache_dir else None
    if cache_path and not refresh and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(), True
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        text = resp.text
    except requests.RequestException as exc:
        print(f"  !! failed to fetch {url}: {exc}", file=sys.stderr)
        return None, False
    if cache_path and cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return text, True


def discover_links(index_text):
    """Return list of (url, filename) for quarterly listing pages."""
    soup = BeautifulSoup(index_text, "html.parser")
    out = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if re.search(r"d\.called\..*\.(?:html|txt)$", href, re.I):
            full = urljoin(BASE_URL, href)
            fname = href.rsplit("/", 1)[-1]
            if full not in seen:
                seen.add(full)
                out.append((full, fname))
    return out


def year_from_filename(fname):
    m = re.search(r"d\.called\.(\d{4})\.", fname)
    if m:
        return int(m.group(1))
    m = re.search(r"d\.called\D*?(\d{2})[.\-]", fname)
    if m:
        yy = int(m.group(1))
        return yy + 1900 if yy < 100 else yy
    return None


SMALL_WORDS = {
    "a", "an", "and", "the", "of", "in", "on", "at", "to", "for", "with",
    "by", "or", "from", "be", "me", "my", "all", "our", "out", "both",
    "these", "those", "ye", "up", "upon", "is", "as", "into", "over",
    "after", "before", "o'",
}

ABBREVIATIONS = {"MA", "VT", "NY", "NYC", "NJ", "CA", "DC", "MD", "PA", "MI",
                 "UK", "USA", "ECD", "FSGW"}

DANCE_CASE_FIXES = {
    "Ha'Penny": "Ha'penny",
    "H'Penny": "H'penny",
}

# Source typos where a whole title (or its leading word) is missing.
DANCE_NAME_FIXES = {
    "'s Round O": "Hambleton's Round O",
}

CALLER_ALIASES = {
    "andrea netleton": "Andrea Nettleton",
    "andrea nettelton": "Andrea Nettleton",
    "ann fallown": "Ann Fallon",
    "bob farrel": "Bob Farrall",
    "bob farrell": "Bob Farrall",
    "diane schmidt": "Diane Schmit",
    "kappy lanning": "Kappy Laning",
    "liz dondalson": "Liz Donaldson",
    "mellissa running": "Melissa Running",
    "martha siegel": "Martha Seigel",
    "martha siegle": "Martha Seigel",
    "tom splisbury": "Tom Spilsbury",
    "may friday": "Mary Kay Friday",
    "dan gillespe": "Dan Gillespie",
    "dan gilespie": "Dan Gillespie",
    "melissa runningand": "Melissa Running",
    "april blum tina chancey": "April Blum",
    "diane schmit liz donaldson": "Diane Schmit",
    "martha seigel liz donaldson": "Martha Seigel",
    "feb 2 - ann fallon": "Ann Fallon",
}

CALLER_DROP = {
    "composer", "coordinator", "ny", "queens",
    "thanks to the following for filling-in for a caller who was",
}


def canonical_dance(name):
    """Normalize a dance title's case and punctuation so duplicates merge."""
    name = (name.replace("\u2019", "'").replace("\u2018", "'")
                .replace("\u201c", '"').replace("\u201d", '"'))
    for wrong, right in DANCE_CASE_FIXES.items():
        name = name.replace(wrong, right)
    tokens = name.split()
    out = []
    for i, t in enumerate(tokens):
        low = t.casefold()
        if i > 0 and low in SMALL_WORDS:
            out.append(low)
        else:
            out.append(t[:1].upper() + t[1:])
    return " ".join(out)


def _title_tokens(text):
    out = []
    for i, t in enumerate(text.split()):
        low = t.casefold()
        if i > 0 and low in SMALL_WORDS:
            out.append(low)
        else:
            out.append(t[:1].upper() + t[1:].lower())
    return " ".join(out)


def _fix_abbrevs(text):
    return re.sub(r"\b(ma|vt|ny|nyc|nj|ca|dc|md|pa|mi|uk|usa|ecd|fsgw)\b",
                  lambda m: m.group(1).upper(), text, flags=re.I)


def canonical_caller_name(s):
    """Canonicalize a single caller name (alias, drop, case)."""
    s = re.sub(r"\s+", " ", s).strip(" \t,;.\u2013\u2014")
    if not s:
        return ""
    s = strip_annotation(s)
    s = s.strip(" \t,;.\u2013\u2014")
    if not s:
        return ""
    low = s.casefold()
    if low in CALLER_DROP:
        return ""
    if "colin hume" in low:
        return "Colin Hume"
    if low in CALLER_ALIASES:
        return CALLER_ALIASES[low]
    m = re.match(r"^(.*?)\s*(\([^()]*\))\s*$", s)
    if m:
        result = _title_tokens(m.group(1)) + " (" + m.group(2)[1:-1].lower() + ")"
    else:
        result = _title_tokens(s)
    return _fix_abbrevs(result).strip()


def clean_dance_name(raw):
    """Return (name, first_after_break, starred)."""
    name = raw.replace("\u00a0", " ").strip()
    first_after_break = False
    starred = False
    if name.startswith("~"):
        first_after_break = True
        name = name[1:].strip()
    while name and name[-1] in "*\u2217\u2020\u2021":
        starred = True
        name = name[:-1].strip()
    # Strip a leading symbol/numeral footnote marker like "(π)".
    name = re.sub(r"^\(\s*[^A-Za-z]*\s*\)\s*", "", name).strip()
    # Strip a caller-initial tag like "(A)", "(AB)", "(AR - coordinator)".
    name = re.sub(r"\s*\([A-Z]{1,3}\s*(?:-\s*\w+)?\)$", "", name).strip()
    for wrong, right in DANCE_NAME_FIXES.items():
        if name.casefold() == wrong.casefold():
            name = right
            break
    name = canonical_dance(name)
    return name, first_after_break, starred


# Lines that are annotations, footnotes, break markers, or separators rather
# than dance titles. These leak into the dance field unless filtered out.
NOTE_LINE_RES = [
    re.compile(r"^[\s\-–—_=*\u2217\u2020\u2021]+$"),   # separators / dashes
    re.compile(r"^[-–—]{2,}"),                         # "--" / "—" notes
    re.compile(r"^\*+"),                                # footnote markers
    re.compile(r"^and\b", re.I),                        # "and Rufty Tufty"
    re.compile(r"^by\b", re.I),                         # "by Graham Christian"
    re.compile(r"^(?:ch|co)\s*:", re.I),                # "Ch:" / "Co:" notes
    re.compile(r"^note\s*:?", re.I),
    re.compile(r"^(?:also\s+known\s+as|alternate\s+version|premier|premiere)\b",
               re.I),
    re.compile(r"^(?:break|dessert|midnight|champagne)\b", re.I),
    re.compile(r"^\([^()]*\)\s*$"),                     # "(It snowed ...)"
    re.compile(r":\s*$"),                               # "…Handout / label:"
]


def is_note_line(text):
    """True if a stripped line is a note/annotation, not a dance title."""
    s = (text or "").replace("\u00a0", " ").strip()
    if s.startswith("~"):
        s = s[1:].strip()
    if not s:
        return True
    return any(rx.match(s) for rx in NOTE_LINE_RES)


def split_callers(caller):
    # Split on "and" / "&" first.
    parts = re.split(r"\s+and\s+|\s*&\s*", caller, flags=re.I)
    out = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # "A (A), B (W), C (K)" multi-caller lists: split on commas when every
        # segment looks like a capitalized name (possibly with a letter tag).
        segments = [s.strip() for s in part.split(",") if s.strip()]
        if len(segments) > 1 and all(
                re.match(r"^[A-Z][\w' .\-\u2013]*(?:\s*\([A-Za-z]{1,3}[^)]*\))?$", s)
                for s in segments):
            for s in segments:
                s = canonical_caller_name(s)
                if s:
                    out.append(s)
        else:
            s = canonical_caller_name(part)
            if s:
                out.append(s)
    return out


def strip_annotation(s):
    """Remove a trailing letter tag like "(A)", "(AR - coordinator)". Does not
    touch descriptive tags like "(guest caller from VT)"."""
    s = s.strip()
    s = re.sub(r"\s*\([A-Z]{1,3}\s*(?:-\s*\w+)?\)\s*$", "", s)
    s = re.sub(r"\s*\(\s*co-?ordinator\s*\)\s*$", "", s, flags=re.I)
    return s.strip(" ,;")


INSTRUMENT_RE = re.compile(
    r"\((?:fiddle|violin|piano|cello|flute|recorder|mandolin|guitar|accordion|"
    r"concertina|bassoon|oboe|dulcimer|trumpet|bass|winds|whistle|melodeon|"
    r"bouzouki|harp|pipes)\b", re.I)


def clean_caller(caller):
    """Trim musician text that leaked into the caller field (source typos)."""
    if not caller:
        return ""
    c = re.sub(r"^\d+\s+", "", caller)  # "3 Stephanie Smith" -> "Stephanie Smith"
    # Cut at a leaked music label ("... Musicians: ..." / "Musicans:" etc.).
    c = re.split(r"\s+(?:Musicians?|Musican|Muscians|Musicans|Musians|Musics|Music)\s*:?",
                 c, maxsplit=1, flags=re.I)[0]
    # Cut at the first instrument parenthetical, e.g. "April Blum ... (fiddle)".
    c = INSTRUMENT_RE.split(c, maxsplit=1)[0]
    # Drop a trailing "Live" / "LIVE!" marker.
    c = re.sub(r"\s+[-–—]?\s*Live\s*!?$", "", c, flags=re.I)
    # Drop a trailing lesson annotation ("— 7:30 Lesson" / "Lesson: Bob").
    c = re.sub(r"\s*[;,–—-]*\s*(?:7:30\s*)?Lesson.*$", "", c, flags=re.I)
    # Drop a trailing "…who will also teach the Lesson" note.
    c = re.sub(r"\s*,?\s*who will also teach\b.*$", "", c, flags=re.I)
    # Drop a trailing "; note" clause ("Mary Kay Friday; Guest caller: ...").
    c = c.split(";", 1)[0].strip()
    return c.strip(" ,;")


def parse_info(info_text):
    """Extract caller, music, host from an info blob.

    Labels are occasionally lower-case ("caller:") or misspelled
    ("Muscians:", "Musicans:"), so matching is case-insensitive and the
    colon after the label is the reliable anchor.
    """
    info_text = info_text.replace("\u00a0", " ").strip()
    caller = ""
    music = ""
    host = ""
    m = re.search(
        r"(?:Musicians?|Musicans?|Muscians?|Music)\s*:\s*(.*?)(?=\s+Host\s*:|$)",
        info_text, re.I | re.S)
    if m:
        music = re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(
        r"Callers?\s*:\s*(.*?)(?=\s+(?:Musicians?|Musicans?|Muscians?|Music|Host)\s*:|$)",
        info_text, re.I | re.S)
    if m:
        caller = re.sub(r"\s+", " ", m.group(1)).strip()
        # Strip a repeated/leaked "Caller(s):" label (source typos).
        caller = re.sub(r"^(?:Callers?\s*:?\s*)+", "", caller, flags=re.I).strip()
        # Source occasionally leaves the caller blank, so the next label
        # ("Music: ...") leaks into the caller slot; recover the real name.
        m2 = re.match(r"^(?:Music|Musicians|Host)\s*:\s*(.*)$", caller, re.I | re.S)
        if m2:
            real = m2.group(1).strip()
            if music and music.lower() == real.lower():
                music = ""
            caller = real
        # A stray "note: ..." is not a caller.
        if re.match(r"^note\s*:", caller, re.I):
            caller = ""
    m = re.search(
        r"Host\s*:\s*(.*?)(?=\s+(?:Musicians?|Musicans?|Muscians?|Music)\s*:|$)",
        info_text, re.I | re.S)
    if m:
        host = re.sub(r"\s+", " ", m.group(1)).strip()
    return caller, music, host


def music_type(music):
    if not music:
        return None
    if re.search(r"\brecorded\b", music, re.I):
        return "recorded"
    return "live"


# --------------------------------------------------------------------------- #
# HTML parsing
# --------------------------------------------------------------------------- #

def parse_date_th(text):
    """Parse a '<th colspan=...>Month Day</th>' header -> (month, day)."""
    text = re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()
    m = re.match(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                 r"[a-z]*\.?\s+(\d{1,2})\b", text, re.I)
    if m:
        return MONTHS[m.group(1).lower()[:3]], int(m.group(2))
    return None


def parse_html(html_text, year, url):
    soup = BeautifulSoup(html_text, HTML_PARSER)
    records = []
    current_month = None
    current_day = None

    for table in soup.find_all("table", class_="tbl"):
        for tr in table.find_all("tr"):
            ths = tr.find_all("th", recursive=False)
            tds = tr.find_all("td", recursive=False)

            # Month header: <th rowspan=...>January</th>
            for th in ths:
                if th.get("rowspan"):
                    mname = re.sub(r"\s+", "", th.get_text(" ", strip=True)).lower()
                    if mname[:3] in MONTHS:
                        current_month = MONTHS[mname[:3]]

            # Date header (old pages): <th colspan=...>January 2</th>
            for th in ths:
                if th.get("colspan") is not None:
                    md = parse_date_th(th.get_text(" ", strip=True))
                    if md:
                        current_month, current_day = md

            # Day cell: <th>2</th> (may carry annotations like "26 After-noon Dance")
            for th in ths:
                t = th.get_text(" ", strip=True)
                m = re.match(r"(\d{1,2})\b", t)
                if m:
                    current_day = int(m.group(1))
                    break

            if not tds or current_month is None or current_day is None:
                continue

            caller, music, host = parse_info(cell_text(tds[0]))
            mtype = music_type(music)

            notes = []
            for cls in ("fineprint", "sml"):
                for fp in tr.find_all(class_=cls):
                    notes.append(fp.get_text(" ", strip=True))

            for set_i, td in enumerate(tds[1:], start=1):
                pos = 0
                for dance, brk, star in dance_cells(td):
                    pos += 1
                    records.append(make_record(
                        year=year, month=current_month, day=current_day,
                        caller=caller, music=music, mtype=mtype, host=host,
                        dance=dance, set_i=set_i, pos=pos,
                        brk=brk, star=star, notes=notes, url=url))
    return records


def cell_text(td):
    for br in td.find_all("br"):
        br.replace_with(" ")
    return td.get_text(" ", strip=True)


def dance_cells(td):
    """Yield (dance_name, first_after_break, starred) for a dance cell."""
    # Remove note markup first: fineprint/sml blocks, plus bordered "Note:"
    # boxes (e.g. "this dance was conducted at Ballroom Blum").
    for cls in ("fineprint", "sml"):
        for tag in td.find_all(class_=cls):
            tag.decompose()
    for div in td.find_all("div"):
        if "border" in (div.get("style") or "").lower():
            div.decompose()
    for sup in td.find_all("sup"):
        sup.decompose()
    for br in td.find_all("br"):
        br.replace_with("\n")
    text = td.get_text("")
    items = []  # [name, first_after_break, starred]
    for line in text.split("\n"):
        line = line.replace("\u00a0", " ").strip()
        if not line:
            continue
        if is_note_line(line):
            continue
        name, brk, star = clean_dance_name(line)
        if name and not re.match(r"^(?:Callers?|Musicians?|Music|Prompters?|Host)\b",
                                 name, re.I):
            items.append([name, brk, star])
    return items


# --------------------------------------------------------------------------- #
# Plain-text parsing
# --------------------------------------------------------------------------- #

def match_date(line):
    s = line.strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})\b", s)
    if m:
        mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yy < 100:
            yy += 1900
        return mm, dd, yy
    m = re.match(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                 r"[a-z]*\.?\s+(\d{1,2})\b", s, re.I)
    if m:
        return MONTHS[m.group(1).lower()[:3]], int(m.group(2)), None
    return None


def split_blocks(lines):
    blocks, cur = [], []
    for ln in lines:
        s = ln.strip()
        if len(s) >= 8 and s.count("_") >= 8 and all(c in "_ " for c in s):
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    return blocks


META_RE = re.compile(
    r"^(?:Callers?|Musicians?|Music|Prompters?|Host)\b|"
    r"^Program\s+provided\b|^Practice\s+Session\b|"
    r"^Break\s+for\b|^Close\s+with\b|^Callers?\s+note\b",
    re.I)


def is_meta_line(s):
    return bool(META_RE.match(s.strip()))


def _infer_columns(stripped_lines):
    """Infer the start offsets of columns 2 and 3 from well-aligned lines.

    Text listings align dance titles into two or three columns separated by
    runs of 2+ spaces. When a title is too long the author sometimes leaves
    only a single space, merging the next column into it; the inferred
    boundary lets us recover the split.
    """
    col2 = {}
    col3 = {}
    for s in stripped_lines:
        gaps = list(re.finditer(r"\s{2,}", s))
        if len(gaps) >= 1:
            col2[gaps[0].end()] = col2.get(gaps[0].end(), 0) + 1
        if len(gaps) >= 2:
            col3[gaps[1].end()] = col3.get(gaps[1].end(), 0) + 1

    def _mode(d):
        if not d:
            return None
        pos = max(d, key=lambda k: (d[k], -k))
        return pos if d[pos] >= 2 else None

    return _mode(col2), _mode(col3)


def _split_dance_columns(stripped, col2, col3):
    parts = [c.strip() for c in re.split(r"\s{2,}", stripped) if c.strip()]
    # If the first title overruns the inferred column-2 boundary because the
    # source used a single space there, split it back apart.
    if (col2 and parts and len(parts[0]) > col2
            and 0 < col2 <= len(stripped) and stripped[col2 - 1] == " "):
        left = parts[0][:col2 - 1].strip()
        right = parts[0][col2:].strip()
        if left and right:
            parts = [left, right] + parts[1:]
    return parts


def parse_block(block, year_hint, url):
    date_line_idx = -1
    date_match = None
    for idx, ln in enumerate(block):
        m = match_date(ln)
        if m:
            date_line_idx = idx
            date_match = m
            break
    if date_match is None:
        return []

    month, day, explicit_year = date_match
    year = explicit_year or year_hint

    # Walk the block, splitting metadata lines (Caller/Music/Prompters/etc.)
    # from column-aligned dance lines.
    info_parts = [block[date_line_idx]]
    dance_lines = []
    i = date_line_idx + 1
    while i < len(block):
        ln = block[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        if is_meta_line(s):
            info_parts.append(s)
            i += 1
            # Consume continuation lines (indented, or single-column lists
            # such as a wrapped "Prompters: A, B," list).
            while i < len(block) and block[i].strip():
                cont = block[i]
                cont_s = cont.strip()
                if not cont_s or is_meta_line(cont_s):
                    break
                if len(re.split(r"\s{2,}", cont_s)) > 1:
                    break
                info_parts.append(cont_s)
                i += 1
            continue
        dance_lines.append(ln)
        i += 1

    info = "\n".join(info_parts)
    if re.search(r"\bno dance\b", info, re.I):
        return []
    caller, music, host = parse_info(info)
    mtype = music_type(music)

    # A block with no caller/musician/host info and no meta labels (e.g. a
    # bare "Washington Spring Ball" banner) has no dances worth recording.
    if not caller and not music and not host and not re.search(
            r"(?:Callers?|Musicians?|Musicans?|Music|Prompters?|Host)\s*:",
            info, re.I):
        return []

    # Parse dances from the body (column-aligned text).
    rows = []
    for line in dance_lines:
        s = line.rstrip("\n")
        if not s.strip():
            continue
        stripped = s.strip()
        if is_note_line(stripped):
            continue
        if re.match(r"^\d{1,2}:\d{2}\b", stripped):
            continue  # time marker / break annotation
        if re.match(r"^Close with", stripped, re.I):
            continue
        leading = len(s) - len(s.lstrip())
        rows.append((leading, stripped))

    col2, col3 = _infer_columns([s for _, s in rows])

    columns = [[], [], []]
    for leading, stripped in rows:
        cols = _split_dance_columns(stripped, col2, col3)
        if not cols:
            continue
        if leading > 0 and len(cols) == 1:
            # likely a wrapped continuation of the previous dance name
            appended = False
            for ci in range(len(columns) - 1, -1, -1):
                if columns[ci]:
                    columns[ci][-1] += " " + cols[0]
                    appended = True
                    break
            if not appended:
                columns[0].append(cols[0])
            continue
        for idx, c in enumerate(cols[:3]):
            if is_note_line(c):
                continue
            columns[idx].append(c)

    records = []
    for set_i, col in enumerate(columns, start=1):
        for pos, raw in enumerate(col, start=1):
            name, brk, star = clean_dance_name(raw)
            if not name:
                continue
            if re.match(r"^(?:Callers?|Musicians?|Music|Prompters?|Host)\b",
                        name, re.I):
                continue
            records.append(make_record(
                year=year, month=month, day=day,
                caller=caller, music=music, mtype=mtype, host=host,
                dance=name, set_i=set_i, pos=pos,
                brk=brk, star=star, notes=[], url=url))
    return records


# --------------------------------------------------------------------------- #
# Record assembly
# --------------------------------------------------------------------------- #

def make_record(year, month, day, caller, music, mtype, host,
                dance, set_i, pos, brk, star, notes, url):
    caller = clean_caller(caller)
    callers = split_callers(caller) if caller else []
    caller = " and ".join(callers) if callers else ""
    return {
        "date": "%04d-%02d-%02d" % (year, month, day),
        "year": year,
        "month": month,
        "day": day,
        "callers": callers,
        "caller": caller,
        "music": music or None,
        "music_type": mtype,
        "host": host or None,
        "dance": dance,
        "set": set_i,
        "pos": pos,
        "first_after_break": brk,
        "starred": star,
        "notes": "; ".join(notes) if notes else None,
        "source": url,
    }


def finalize(records):
    """Sort records and assign a flat reading order within each date."""
    records.sort(key=lambda r: (r["date"], r["set"], r["pos"]))
    key = None
    order = 0
    for r in records:
        if r["date"] != key:
            key = r["date"]
            order = 0
        order += 1
        r["order"] = order
    return records


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="crawler/cache",
                    help="Directory for caching raw pages")
    ap.add_argument("--refresh", action="store_true",
                    help="Ignore cache and re-download everything")
    ap.add_argument("--out", default="data/dances.json",
                    help="Output JSON path")
    args = ap.parse_args()

    print("Fetching index: %s" % INDEX_URL)
    index_text, ok = fetch(INDEX_URL, args.cache, args.refresh)
    if not ok:
        sys.exit(1)

    links = discover_links(index_text)
    print("Discovered %d quarterly pages" % len(links))

    all_records = []
    failures = []
    skipped = []
    for url, fname in links:
        year = year_from_filename(fname)
        text, ok = fetch(url, args.cache, args.refresh)
        if not ok:
            failures.append(fname)
            continue
        if fname.lower().endswith(".txt"):
            if re.search(r"<!DOCTYPE|<html", text[:2000], re.I):
                print("  %-34s -> skipped (mislabeled HTML on source)" % fname)
                skipped.append({"file": fname, "reason": "txt file contains HTML"})
                continue
            records = parse_text(text, year, url)
        else:
            records = parse_html(text, year, url)
        all_records.extend(records)
        print("  %-34s -> %4d dances (year=%s)" % (fname, len(records), year))

    all_records = finalize(all_records)

    years = sorted({r["year"] for r in all_records})
    doc = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "source": INDEX_URL,
        "count": len(all_records),
        "years": years,
        "records": all_records,
    }
    if skipped:
        doc["skipped"] = skipped

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))

    print("\nWrote %d dance records across %d years to %s"
          % (len(all_records), len(years), args.out))
    if failures:
        print("Failed pages: %s" % ", ".join(failures))


def parse_text(text, year, url):
    lines = text.splitlines()
    records = []
    for block in split_blocks(lines):
        records.extend(parse_block(block, year, url))
    return records


if __name__ == "__main__":
    main()
