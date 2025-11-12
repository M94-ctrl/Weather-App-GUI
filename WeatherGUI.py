# =========================================================
#  WEATHER APP - Current / Last 7 Days / Last 30 Days
#  Supports input as "City, Country"
#  Shows current weather in GUI console
#  Downloads past data to Excel
#  Author: Shwetank | GPT-5 version
# =========================================================

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import pandas as pd
import datetime
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- Safe GET (auto SSL fallback) ----------
def safe_get(url, **kwargs):
    """Try secure HTTPS first; fallback to verify=False if SSL fails."""
    try:
        return requests.get(url, timeout=20, **kwargs)
    except requests.exceptions.SSLError:
        return requests.get(url, timeout=20, verify=False, **{k: v for k, v in kwargs.items() if k != "verify"})


# ---------- Convert City, Country → Coordinates ----------
def geocode_city(city_country):
    """
    Accepts input as 'City, Country' or just 'City'.
    Returns (latitude, longitude, country).
    """
    parts = [p.strip() for p in city_country.split(",")]
    city = parts[0] if parts else city_country
    country_filter = parts[1] if len(parts) > 1 else None

    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=10"
    r = safe_get(geo_url)
    r.raise_for_status()
    js = r.json()

    if "results" not in js or not js["results"]:
        raise ValueError(f"City not found: {city_country}")

    results = js["results"]

    # Filter by country if provided
    if country_filter:
        matched = [rec for rec in results if rec.get("country", "").lower().startswith(country_filter.lower())]
        rec = matched[0] if matched else results[0]
    else:
        rec = results[0]

    return rec["latitude"], rec["longitude"], rec.get("country", "")


# ---------- Fetch Current Weather ----------
def fetch_current(lat, lon, country, city_country):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    r = safe_get(url)
    r.raise_for_status()
    js = r.json()
    data = js.get("current_weather")
    if not data:
        raise ValueError("No current weather data returned")

    output = [
        "🌤️  Current Weather Details",
        "----------------------------------",
        f"📍 Location: {city_country}",
        f"🌡️ Temperature: {data['temperature']}°C",
        f"🌬️ Wind Speed: {data['windspeed']} km/h",
        f"🧭 Wind Direction: {data['winddirection']}°",
        f"⏰ Time: {data['time']}",
        "----------------------------------",
    ]
    return "\n".join(output)


# ---------- Download Historical Data ----------
def fetch_history(lat, lon, country, city_country, days, folder, status_label):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    hourly_vars = ["temperature_2m", "windspeed_10m", "winddirection_10m", "precipitation"]
    hourly_str = ",".join(hourly_vars)

    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&hourly={hourly_str}&timezone=auto"
    )

    status_label.config(text="📡 Fetching historical data… Please wait…", foreground="blue")
    status_label.update()

    r = safe_get(url)
    r.raise_for_status()
    js = r.json()

    df = pd.DataFrame({"time": js["hourly"]["time"]})
    for var in hourly_vars:
        df[var] = js["hourly"].get(var)

    os.makedirs(folder, exist_ok=True)
    filename = f"{city_country.replace(' ', '_').replace(',', '')}_last{days}days_{datetime.date.today()}.xlsx"
    filepath = os.path.join(folder, filename)
    df.to_excel(filepath, index=False)

    status_label.config(text="✅ File saved successfully!", foreground="green")
    return filepath


# ---------- Run Weather ----------
def run_weather():
    console_box.delete(1.0, tk.END)  # clear previous text
    status_label.config(text="")  # reset status

    city_country = city_entry.get().strip()
    if not city_country:
        messagebox.showerror("Error", "Please enter a city and country (e.g., Delhi, India).")
        return

    mode = mode_var.get()
    folder = None  # don't ask yet

    try:
        status_label.config(text="🌍 Fetching coordinates…", foreground="blue")
        status_label.update()
        lat, lon, country = geocode_city(city_country)

        # --- CURRENT MODE ---
        if mode == "current":
            status_label.config(text="🌤️ Fetching current weather…", foreground="blue")
            status_label.update()
            result = fetch_current(lat, lon, country, city_country)
            console_box.insert(tk.END, result + "\n")
            status_label.config(text="✅ Data fetched successfully!", foreground="green")

        # --- 7 DAYS / MONTH MODES ---
        else:
            # Ask folder only if Excel output required
            folder = filedialog.askdirectory(title="Select folder to save Excel file")
            if not folder:
                status_label.config(text="❌ Cancelled: No folder selected.", foreground="red")
                return

            if mode == "7days":
                filepath = fetch_history(lat, lon, country, city_country, 7, folder, status_label)
                msg = f"✅ 7-Day data saved to Excel:\n{filepath}"
                console_box.insert(tk.END, msg + "\n")

            elif mode == "month":
                filepath = fetch_history(lat, lon, country, city_country, 30, folder, status_label)
                msg = f"✅ 30-Day data saved to Excel:\n{filepath}"
                console_box.insert(tk.END, msg + "\n")

    except Exception as e:
        status_label.config(text=f"❌ Error: {e}", foreground="red")
        console_box.insert(tk.END, f"❌ Error: {e}\n")


# ---------- GUI Setup ----------
root = tk.Tk()
root.title("🌦️ Weather Report (Open-Meteo API)")
root.geometry("540x480")
root.resizable(False, False)

frame = ttk.Frame(root, padding=20)
frame.pack(fill="both", expand=True)

ttk.Label(frame, text="🌍  Weather Report Generator", font=("Segoe UI", 14, "bold")).pack(pady=10)
ttk.Label(frame, text="Enter City, Country (e.g., Delhi, India):").pack(pady=5)

city_entry = ttk.Entry(frame, width=40)
city_entry.insert(0, "Delhi, India")
city_entry.pack(pady=2)

mode_var = tk.StringVar(value="current")
ttk.Label(frame, text="Select Mode:").pack(pady=(10, 5))
modes = [
    ("Current Weather (Show in console)", "current"),
    ("Last 7 Days (Download Excel)", "7days"),
    ("Last 30 Days (Download Excel)", "month"),
]
for text, val in modes:
    ttk.Radiobutton(frame, text=text, variable=mode_var, value=val).pack(anchor="w")

ttk.Button(frame, text="Fetch Weather", command=run_weather).pack(pady=10)

# ---------- GUI Console (Scrollable Text Box) ----------
ttk.Label(frame, text="Console Output:").pack(anchor="w", pady=(5, 2))
console_box = tk.Text(frame, height=10, width=65, wrap="word", font=("Consolas", 10))
console_box.pack(pady=(0, 10))
scrollbar = ttk.Scrollbar(frame, orient="vertical", command=console_box.yview)
console_box.configure(yscrollcommand=scrollbar.set)
scrollbar.place(in_=console_box, relx=1.0, rely=0, relheight=1.0, anchor="ne")

# ---------- Status Line ----------
status_label = ttk.Label(frame, text="", font=("Segoe UI", 9, "italic"))
status_label.pack(pady=(0, 5))

ttk.Label(frame, text="© 2025 Mushtaque - Open-Meteo API", font=("Segoe UI", 8)).pack(side="bottom", pady=5)

root.mainloop()
