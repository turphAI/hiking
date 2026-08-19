"""Weather lookups via Open-Meteo — free, no API key.

Two endpoints depending on how far the date is from today:
- Forecast endpoint (covers today + a `past_days` window + future) for
  recent/upcoming dates.
- Archive endpoint (ERA5 reanalysis) for anything further in the past —
  covers the historical-by-date case (logging a hike after the fact).

Both return the same shape so callers don't care which path was taken.
"""
from datetime import date, timedelta

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_FIELDS = "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"

# WMO weather codes (Open-Meteo's `weathercode`), mapped to plain text —
# https://open-meteo.com/en/docs, "WMO Weather interpretation codes".
_WEATHER_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "light freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "light freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light rain showers", 81: "rain showers", 82: "heavy rain showers",
    85: "light snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm w/ hail", 99: "severe thunderstorm w/ hail",
}


def _describe(code):
    if code is None:
        return None
    return _WEATHER_CODES.get(int(code), f"code {code}")


def _summarize(day):
    """Reduce one day of Open-Meteo `daily` arrays (index 0) into a summary."""
    tmax = day.get("temperature_2m_max", [None])[0]
    tmin = day.get("temperature_2m_min", [None])[0]
    precip = day.get("precipitation_sum", [None])[0]
    code = day.get("weathercode", [None])[0]
    condition = _describe(code)

    parts = []
    if tmax is not None and tmin is not None:
        parts.append(f"{round(tmin)}–{round(tmax)}°F")
    if condition:
        parts.append(condition)
    if precip:
        parts.append(f"{precip}\" precip")
    summary = ", ".join(parts) if parts else None

    return {
        "ok": True,
        "summary": summary,
        "temp_max_f": tmax,
        "temp_min_f": tmin,
        "precip_in": precip,
        "condition": condition,
    }


def get_weather(lat: float, lon: float, date_str: str) -> dict:
    """Fetch a weather summary for a lat/lon + ISO date.

    Returns {"ok": False, "error": ...} on any failure rather than raising —
    weather is a nice-to-have prefill, never a reason to block saving a hike.
    """
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        return {"ok": False, "error": "invalid_date"}

    today = date.today()
    recent_cutoff = today - timedelta(days=5)  # archive API lags a few days

    try:
        if target >= recent_cutoff:
            resp = requests.get(
                FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": DAILY_FIELDS,
                    "temperature_unit": "fahrenheit",
                    "precipitation_unit": "inch",
                    "timezone": "auto",
                    "start_date": date_str,
                    "end_date": date_str,
                    "past_days": min(92, max(0, (today - target).days)),
                },
                timeout=8,
            )
        else:
            resp = requests.get(
                ARCHIVE_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": DAILY_FIELDS,
                    "temperature_unit": "fahrenheit",
                    "precipitation_unit": "inch",
                    "timezone": "auto",
                    "start_date": date_str,
                    "end_date": date_str,
                },
                timeout=8,
            )
        resp.raise_for_status()
        daily = resp.json().get("daily")
        if not daily or not daily.get("time"):
            return {"ok": False, "error": "no_data_for_date"}
        return _summarize(daily)
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}
