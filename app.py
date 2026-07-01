# run [py -m PyInstaller --onefile --noconsole --name FixtureDisplay --add-data "templates;templates" --add-data "static;static" app.py] while in the directory to build
from flask import Flask, render_template, jsonify
import csv
import os
import glob
import sys
import threading
import time
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, messagebox
import json


app = Flask(__name__)

# Anchor the CSV path to this script's own folder, so it works no matter
# what directory you launch "python app.py" from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = None
MATCH_DURATION_MINS = 140   # how long a match "counts" as current/in-progress
DEFAULT_NUM_COURTS = 5

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def get_num_courts():
    """Read num_courts from config.json, falling back to a sane default
    if it's missing or invalid rather than crashing the whole display."""
    try:
        config = load_config()
        n = int(config.get("num_courts", DEFAULT_NUM_COURTS))
        return n if n > 0 else DEFAULT_NUM_COURTS
    except (OSError, ValueError, json.JSONDecodeError):
        return DEFAULT_NUM_COURTS


def select_csv():
    """Find the newest fixtures CSV in the configured downloads folder.
    Shows a friendly popup instead of a silent console exit, since the
    people running this day-to-day aren't using a terminal."""

    global CSV_PATH

    try:
        config = load_config()
        downloads_dir = config["downloads_folder"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        _fatal_startup_error(
            "Settings Problem",
            "config.json is missing or unreadable "
            f"({exc}).\n\nOpen settings.py and click Save Settings to "
            "regenerate it, then try again."
        )
        return

    files = glob.glob(os.path.join(downloads_dir, "*.csv"))

    if not files:
        _fatal_startup_error(
            "No Fixtures Found",
            f"No fixtures CSV was found in:\n{downloads_dir}\n\n"
            "Run fixture-scraper2.py first to download today's fixtures, "
            "then start the display again."
        )
        return

    # Pick newest CSV
    CSV_PATH = max(
        files,
        key=os.path.getmtime
    )


def _fatal_startup_error(title, message):
    """Show a popup for a startup problem, then exit. A plain print() would
    be invisible to someone who launched this by double-clicking, not from
    a terminal."""
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except tk.TclError:
        # No display available (e.g. running headless) -- fall back to console.
        print(f"{title}: {message}")
    sys.exit(1)


# --- Fixture cache -----------------------------------------------------
# Every request used to re-open and re-parse the whole CSV, even though the
# file only actually changes when the scraper runs (occasionally), not on
# every page/API hit (which can be every 1-2s per court on a live display).
#
# Instead, we check the file's mtime+size (a cheap os.stat() call) on each
# request. If it hasn't changed since we last parsed it, we reuse the
# already-parsed list in memory. If it *has* changed, we reload once and
# cache the new result. This keeps things instant when nothing's changed,
# and still picks up scraper updates within a single request (no restart,
# no polling delay).
_cache_lock = threading.Lock()
_cache = {
    "fixtures": [],
    "sig": None,       # (mtime_ns, size) of CSV_PATH as of last successful parse
}


def _read_csv_rows(path):
    """Open and parse the CSV into raw dict rows, with a short retry to ride
    out the rare transient lock (e.g. AV/indexer) right after the scraper's
    atomic os.replace() lands the new file."""
    last_err = None
    for attempt in range(5):
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                return list(csv.DictReader(f))
        except (PermissionError, OSError) as exc:
            last_err = exc
            time.sleep(0.1)
    raise last_err


def _parse_rows(rows):
    """Turn raw CSV dict rows into fixtures with real datetime fields,
    skipping any row that's malformed rather than failing the whole batch."""
    fixtures = []
    for row in rows:
        try:
            start_dt = datetime.strptime(row["datetime"], "%d/%m/%Y %H:%M:%S")
        except (KeyError, ValueError):
            continue
        row["start_dt"] = start_dt
        row["end_dt"] = start_dt + timedelta(minutes=MATCH_DURATION_MINS)
        fixtures.append(row)
    return fixtures


def load_fixtures():
    """Return the current fixture list, reusing the in-memory cache unless
    the CSV on disk has changed since we last parsed it."""
    try:
        st = os.stat(CSV_PATH)
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        # File briefly missing (e.g. mid-replace) -- fall back to whatever
        # we already have cached rather than erroring the whole page out.
        with _cache_lock:
            return _cache["fixtures"]

    # Fast path: nothing changed, no lock needed, no file read.
    if sig == _cache["sig"]:
        return _cache["fixtures"]

    # Slow path: file changed (or this is the first load). Only one thread
    # actually does the reload; others just wait and then reuse its result.
    with _cache_lock:
        # Re-check inside the lock in case another thread already reloaded
        # while we were waiting for it.
        if sig == _cache["sig"]:
            return _cache["fixtures"]

        rows = _read_csv_rows(CSV_PATH)
        fixtures = _parse_rows(rows)
        _cache["fixtures"] = fixtures
        _cache["sig"] = sig
        return fixtures

@app.route("/")
def index():
    fixtures = load_fixtures()

    # Always show Court 1..N per settings, even before any fixtures exist
    # for some of them (e.g. first thing on game day, before the scrape).
    num_courts = get_num_courts()
    courts = [f"Court {i}" for i in range(1, num_courts + 1)]

    # Fold in any court names from the CSV that fall outside that numbered
    # range (e.g. a differently-named venue court), without duplicating.
    seen_lower = {c.lower() for c in courts}
    for f in fixtures:
        name = f.get("court", "")
        if name and name.lower() not in seen_lower:
            courts.append(name)
            seen_lower.add(name.lower())

    return render_template("index.html", courts=courts)

@app.route("/court/<court_name>")
def court(court_name):
    return render_template("court.html", court_name=court_name)
@app.route("/overlay/<court_name>")
def overlay(court_name):
    return render_template(
        "overlay.html",
        court_name=court_name
    )

@app.route("/api/court/<court_name>")
def court_api(court_name):

    fixtures = load_fixtures()

    court_fixtures = [
        f for f in fixtures
        if f["court"].lower() == court_name.lower()
    ]
    court_fixtures.sort(key=lambda f: f["start_dt"])

    now = datetime.now()

    current = None
    next_match = None

    for f in court_fixtures:

        if f["start_dt"] <= now < f["end_dt"]:
            current = {
                "league": f["league"],
                "team_a": f["team_a"],
                "team_b": f["team_b"],
                "time": f["start_dt"].strftime("%H:%M")
            }


        elif f["start_dt"] > now and next_match is None:
            next_match = {
                "league": f["league"],
                "team_a": f["team_a"],
                "team_b": f["team_b"],
                "time": f["start_dt"].strftime("%H:%M"),
                "date": f["start_dt"].strftime("%d %b"),
                "countdown": max(
                    0,
                    int((f["start_dt"] - now).total_seconds())
                )
            }
    
    try:
        csv_updated = datetime.fromtimestamp(
            os.path.getmtime(CSV_PATH)
        ).strftime("%H:%M:%S")
    except OSError:
        csv_updated = None

    return jsonify({
        "current": current,
        "next": next_match,
        "clock": now.strftime("%A %d %B %Y • %H:%M:%S"),
        "fixtures_updated": csv_updated
    })

if __name__ == "__main__":

    select_csv()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )