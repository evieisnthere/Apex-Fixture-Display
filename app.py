# run [py -m PyInstaller --onefile --noconsole --name FixtureDisplay --add-data "templates;templates" --add-data "static;static" app.py] while in the directory to build
from flask import Flask, render_template, jsonify
import csv
import os
import threading
import time
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog
import json


app = Flask(__name__)

# Anchor the CSV path to this script's own folder, so it works no matter
# what directory you launch "python app.py" from.
CSV_PATH = None
MATCH_DURATION_MINS = 140   # how long a match "counts" as current/in-progress

def select_csv():

    global CSV_PATH

    root = tk.Tk()
    root.withdraw()

    CSV_PATH = filedialog.askopenfilename(
        title="Select Fixtures CSV",
        filetypes=[
            ("CSV Files", "*.csv"),
            ("All Files", "*.*")
        ]
    )

    root.destroy()

    if not CSV_PATH:
        exit()


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
    seen = []
    for f in fixtures:
        if f["court"] not in seen:
            seen.append(f["court"])
    return render_template("index.html", courts=seen)

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
    
    return jsonify({
        "current": current,
        "next": next_match,
        "clock": now.strftime("%A %d %B %Y • %H:%M:%S")
    })

if __name__ == "__main__":

    select_csv()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )