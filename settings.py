import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os


CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "config.json"
)


DEFAULT_CONFIG = {
    "downloads_folder": "Z:\\",
    "num_courts": 5,
    "leagues": [
        {
            "name": "U/22 Womens",
            "url": "https://cricketaustralia.spawtz.com/Leagues/Fixtures?LeagueId=5&SeasonId=10&DivisionId=171"
        },
        {
            "name": "U/22 Mens",
            "url": "https://cricketaustralia.spawtz.com/Leagues/Fixtures?LeagueId=5&SeasonId=10&DivisionId=170"
        },
        {
            "name": "Open Womens",
            "url": "https://cricketaustralia.spawtz.com/Leagues/Fixtures?LeagueId=5&SeasonId=10&DivisionId=169"
        },
        {
            "name": "Open Mens",
            "url": "https://cricketaustralia.spawtz.com/Leagues/Fixtures?LeagueId=5&SeasonId=10&DivisionId=168"
        }
    ]
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config():

    try:
        num_courts = int(num_courts_var.get())
        if num_courts < 1:
            raise ValueError
    except (ValueError, tk.TclError):
        messagebox.showerror(
            "Invalid Number of Courts",
            "Number of Courts must be a whole number of 1 or more."
        )
        return

    config = {
        "downloads_folder": folder_var.get(),
        "num_courts": num_courts,
        "leagues": []
    }

    for row in league_rows:
        name = row["name"].get().strip()
        url = row["url"].get().strip()

        if name and url:
            config["leagues"].append({
                "name": name,
                "url": url
            })

    with open(CONFIG_FILE, "w") as f:
        json.dump(
            config,
            f,
            indent=4
        )

    messagebox.showinfo(
        "Saved",
        "Settings saved successfully."
    )


def reset_defaults():

    answer = messagebox.askyesno(
        "Reset Settings",
        "Return all settings to default?"
    )

    if not answer:
        return

    with open(CONFIG_FILE, "w") as f:
        json.dump(
            DEFAULT_CONFIG,
            f,
            indent=4
        )

    messagebox.showinfo(
        "Reset",
        "Settings restored to default."
    )

    root.destroy()
    os.startfile(__file__)


def browse_folder():

    folder = filedialog.askdirectory()

    if folder:
        folder_var.set(folder)


def add_league(name="", url=""):

    frame = tk.Frame(league_frame)
    frame.pack(fill="x", pady=3)

    name_var = tk.StringVar(value=name)
    url_var = tk.StringVar(value=url)


    tk.Entry(
        frame,
        textvariable=name_var,
        width=20
    ).pack(side="left", padx=5)


    tk.Entry(
        frame,
        textvariable=url_var,
        width=70
    ).pack(side="left", padx=5)


    row = {
        "frame": frame,
        "name": name_var,
        "url": url_var
    }


    def remove():

        if row in league_rows:
            league_rows.remove(row)

        frame.destroy()


    tk.Button(
        frame,
        text="Remove",
        command=remove
    ).pack(side="left")


    league_rows.append(row)



# --------------------------
# UI
# --------------------------

config = load_config()

root = tk.Tk()
root.title("Fixture Downloader Settings")
root.geometry("900x500")


# Folder

tk.Label(
    root,
    text="Download Folder:"
).pack(anchor="w", padx=10)


folder_var = tk.StringVar(
    value=config.get("downloads_folder", "")
)


folder_box = tk.Frame(root)
folder_box.pack(fill="x", padx=10)


tk.Entry(
    folder_box,
    textvariable=folder_var,
    width=70
).pack(side="left")


tk.Button(
    folder_box,
    text="Browse",
    command=browse_folder
).pack(side="left", padx=5)



# Number of courts

tk.Label(
    root,
    text="Number of Courts:"
).pack(anchor="w", padx=10, pady=(15, 0))


num_courts_box = tk.Frame(root)
num_courts_box.pack(fill="x", padx=10)


num_courts_var = tk.StringVar(
    value=str(config.get("num_courts", DEFAULT_CONFIG["num_courts"]))
)


tk.Spinbox(
    num_courts_box,
    from_=1,
    to=50,
    width=5,
    textvariable=num_courts_var
).pack(side="left")


tk.Label(
    num_courts_box,
    text="  This controls how many court links show on the display's home page "
         "(e.g. Court 1 through Court N), even before fixtures exist for all of them.",
    fg="gray40",
    wraplength=650,
    justify="left"
).pack(side="left", padx=5)



# Leagues

tk.Label(
    root,
    text="Leagues:"
).pack(anchor="w", padx=10, pady=(15,0))


league_frame = tk.Frame(root)
league_frame.pack(
    fill="both",
    expand=True,
    padx=10
)


league_rows = []


for league in config.get("leagues", []):

    add_league(
        league.get("name", ""),
        league.get("url", "")
    )



tk.Button(
    root,
    text="Add League",
    command=add_league
).pack(pady=5)


tk.Button(
    root,
    text="Save Settings",
    command=save_config,
    height=2
).pack(pady=5)


tk.Button(
    root,
    text="Return to Default",
    command=reset_defaults,
    height=2
).pack(pady=5)


root.mainloop()