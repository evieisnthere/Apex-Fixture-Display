# run [py -m PyInstaller --onefile --noconsole --name FixtureDisplay --add-data "templates;templates" --add-data "static;static" app.py] while in the directory to build
from flask import Flask, render_template, jsonify
import csv
import os
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog
import json


app = Flask(__name__)

# Anchor the CSV path to this script's own folder, so it works no matter
# what directory you launch "python app.py" from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = None
MATCH_DURATION_MINS = 180   # how long a match "counts" as current/in-progress

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


def load_fixtures():
    """Read the CSV and parse each row's datetime string into a real datetime object."""
    fixtures = []
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            start_dt = datetime.strptime(row["datetime"], "%d/%m/%Y %H:%M:%S")
            row["start_dt"] = start_dt
            row["end_dt"] = start_dt + timedelta(minutes=MATCH_DURATION_MINS)
            fixtures.append(row)
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