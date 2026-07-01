import csv
import os
import re
import sys
import tempfile
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

PAGES = [
    {
        "url": "https://cricketaustralia.spawtz.com/Leagues/Fixtures?LeagueId=5&SeasonId=10&DivisionId=171",
        "league": "U/22 Womens",
    },
     {
         "url": "https://cricketaustralia.spawtz.com/Leagues/Fixtures?LeagueId=5&SeasonId=10&DivisionId=170",
         "league": "U/22 Mens",
    },
     {
         "url": "https://cricketaustralia.spawtz.com/Leagues/Fixtures?LeagueId=5&SeasonId=10&DivisionId=169",
         "league": "Open Womens",
    },
     {
         "url": "https://cricketaustralia.spawtz.com/Leagues/Fixtures?LeagueId=5&SeasonId=10&DivisionId=168",
         "league": "Open Mens",
    },        
]

OUTPUT_FILENAME = "fixtures_combined.csv"

# _downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
_downloads_dir = "Z:"
if os.path.isdir(_downloads_dir):
    OUTPUT_CSV = os.path.join(_downloads_dir, OUTPUT_FILENAME)
else:
    OUTPUT_CSV = OUTPUT_FILENAME


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}

# Recognised state / territory codes. Add more here if a different
# competition uses other team naming (e.g. club names).
STATE_CODES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]

DATE_RE = re.compile(
    r"\b(Mon|Tues|Tue|Wed|Wednes|Thu|Thurs|Fri|Sat|Satur|Sun)\w*day\s+"
    r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b"
)
TIME_RE = re.compile(r"\b(\d{1,2}:\d{2}\s*[APap]\.?[Mm]\.?)\b")
COURT_RE = re.compile(r"\bCourt\s*\d+\b", re.IGNORECASE)


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_date_heading(text: str):
    """Parse a heading like 'Wednesday 01 Jul 2026' -> datetime.date"""
    m = DATE_RE.search(text)
    if not m:
        return None
    day, month_str, year = m.group(2), m.group(3), m.group(4)
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(f"{day} {month_str} {year}", fmt).date()
        except ValueError:
            continue
    return None


def parse_time(text: str):
    """Parse a time like '1:00PM' / '1:00 PM' -> datetime.time"""
    m = TIME_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(" ", "").upper()
    for fmt in ("%I:%M%p",):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None


def extract_state(team_text: str) -> str:
    """Pull a state/territory code out of a team name like 'NSW U22W'."""
    text = team_text.strip().upper()
    for code in STATE_CODES:
        if text == code or text.startswith(code + " ") or text.startswith(code):
            return code
    return text.split()[0] if text.split() else text


def row_cells_text(tr) -> list:
    return [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]


def parse_fixtures(html: str, league: str) -> list:
    """Parse a Spawtz-style fixtures page into a list of fixture dicts."""
    soup = BeautifulSoup(html, "html.parser")
    rows_out = []

    current_date = None

    for tr in soup.find_all("tr"):
        cells = row_cells_text(tr)
        if not cells:
            continue
        full_text = " ".join(cells)

        maybe_date = parse_date_heading(full_text)
        if maybe_date and len(cells) <= 2:
            current_date = maybe_date
            continue

        time_val = parse_time(full_text)
        court_match = COURT_RE.search(full_text)
        team_links = [
            a.get_text(strip=True)
            for a in tr.find_all("a")
            if a.get_text(strip=True)
        ]

        if current_date and time_val and court_match and len(team_links) >= 2:
            team_a = extract_state(team_links[0])
            team_b = extract_state(team_links[1])
            dt = datetime.combine(current_date, time_val)
            rows_out.append(
                {
                    "datetime": dt.strftime("%d/%m/%Y %H:%M:%S"),
                    "team_a": team_a,
                    "team_b": team_b,
                    "court": court_match.group(0).title(),
                    "league": league,
                }
            )

    return rows_out


def scrape_all(pages) -> list:
    all_rows = []
    for page in pages:
        url, league = page["url"], page["league"]
        print(f"Fetching: {url}  [{league}]", file=sys.stderr)
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            print(f"  ! Failed to fetch {url}: {exc}", file=sys.stderr)
            continue

        rows = parse_fixtures(html, league)
        print(f"  -> found {len(rows)} fixtures", file=sys.stderr)
        all_rows.extend(rows)

        time.sleep(1)

    return all_rows


def write_csv(rows, path):
    seen = set()
    deduped = []
    for r in rows:
        key = (r["datetime"], r["team_a"], r["team_b"], r["court"], r["league"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    deduped.sort(
        key=lambda r: (
            datetime.strptime(r["datetime"], "%d/%m/%Y %H:%M:%S"),
            r["league"],
            r["court"],
        )
    )

    # Write to a temp file in the SAME directory as the target, then
    # atomically replace the target with it. This means a reader (e.g. the
    # Flask app, polling this file) only ever sees either the fully-old
    # file or the fully-new file -- never a half-written one. That's what
    # lets app.py reload fixtures live without needing a restart.
    target_dir = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(
        dir=target_dir, prefix=".fixtures_tmp_", suffix=".csv"
    )
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["datetime", "team_a", "team_b", "court", "league"]
            )
            writer.writeheader()
            writer.writerows(deduped)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def main():
    if not PAGES:
        print("No pages configured. Edit the PAGES list in this script.", file=sys.stderr)
        sys.exit(1)

    rows = scrape_all(PAGES)
    if not rows:
        print("No fixtures found. The page structure may differ from what "
              "this script expects -- check parse_fixtures().", file=sys.stderr)
        sys.exit(1)

    write_csv(rows, OUTPUT_CSV)
    print(f"Wrote {len(rows)} fixtures to {os.path.abspath(OUTPUT_CSV)}")


if __name__ == "__main__":
    main()