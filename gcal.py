"""
JARVIS - Google Calendar helper (Milestone 3).

ONE job: take a title + date + time that Claude already parsed, and create a
real event on your Google Calendar at the correct EASTERN time. Then hand back
a link and a clean confirmation of exactly what got written.

How it talks to Google:
  - It logs in as the "robot" service account using the key file
    `service_account.json` that lives next to this file.
  - You already shared your calendar with that robot and gave it
    "Make changes to events", so it's allowed to write.
  - Nothing here ever opens a browser or expires - that's why we chose a
    service account.

The timezone trick (so 3pm means 3pm, not some UTC mistake):
  We hand Google the LOCAL time as plain text ("2026-06-16T15:00:00") AND,
  separately, the timezone NAME ("America/New_York"). Google does the math.
  We never convert to UTC by hand - that's where timezone bugs come from.
"""

import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

# Which calendar to write to (your gmail address = your main calendar).
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

# There are TWO ways to give JARVIS the robot's key, and it tries them in order:
#   1. On a server (Railway): set the whole key file's CONTENTS as the
#      environment variable GOOGLE_SERVICE_ACCOUNT_JSON. Nothing lives on disk.
#   2. On your laptop: leave that env var unset and keep service_account.json
#      sitting next to this script (the original setup). The code falls back to it.
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

# We only ask for permission to manage events - nothing more (least privilege).
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# Your timezone, pinned. America/New_York = Eastern = NYC and Philadelphia both.
TZ_NAME = "America/New_York"

if not CALENDAR_ID:
    raise SystemExit("No GOOGLE_CALENDAR_ID found in .env")
# We need EITHER the env-var key (server) OR the key file (laptop). If we have
# neither, we can't talk to Google at all - stop now with a clear message.
if not SERVICE_ACCOUNT_JSON and not os.path.exists(SERVICE_ACCOUNT_FILE):
    raise SystemExit(
        "No Google key found. Set GOOGLE_SERVICE_ACCOUNT_JSON (server) or put "
        f"service_account.json next to this file ({SERVICE_ACCOUNT_FILE})."
    )


def _credentials():
    """Build the robot's Google credentials from whichever source is available.

    Prefer the environment variable (the server way - key comes from a setting,
    not a file); otherwise read the local key file (the laptop way)."""
    if SERVICE_ACCOUNT_JSON:
        info = json.loads(SERVICE_ACCOUNT_JSON)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )


def _service():
    """Log in as the robot and return a connection to the Calendar API."""
    return build("calendar", "v3", credentials=_credentials(), cache_discovery=False)


def create_event(title: str, date_str: str, time_str: str, duration_minutes: int = 60) -> dict:
    """
    Create one event and return a dict:
        {"link": <url>, "confirmed_when": <pretty ET string>, "id": <event id>}

    date_str: 'YYYY-MM-DD'   time_str: 'HH:MM' (24-hour)
    Events default to 60 minutes long.
    """
    # Build the start time as a *local* (Eastern) wall-clock time.
    start_local = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    end_local = start_local + timedelta(minutes=duration_minutes)

    event_body = {
        "summary": title,
        # dateTime is the plain local time; timeZone tells Google how to read it.
        "start": {"dateTime": start_local.isoformat(), "timeZone": TZ_NAME},
        "end": {"dateTime": end_local.isoformat(), "timeZone": TZ_NAME},
    }

    created = _service().events().insert(calendarId=CALENDAR_ID, body=event_body).execute()

    # A human-readable echo of EXACTLY what we wrote, e.g. "Tue Jun 16, 3:00 PM ET".
    pretty_time = start_local.strftime("%I:%M %p").lstrip("0")  # '3:00 PM'
    confirmed_when = start_local.strftime("%a %b %d, ") + pretty_time + " ET"

    return {
        "link": created.get("htmlLink", ""),
        "confirmed_when": confirmed_when,
        "id": created.get("id", ""),
    }


def delete_event(event_id: str) -> None:
    """Remove an event by its id (used by the 'undo' command in the bot)."""
    _service().events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()


def update_event(event_id: str, new_date: str = "", new_time: str = "", new_title: str = "") -> dict:
    """
    Change an EXISTING event in place (not delete + recreate) and return a dict:
        {"link": <url>, "confirmed_when": <pretty ET string>, "id": <event id>}

    This is what makes 'actually make it 4pm' move the same event instead of
    creating a duplicate. You can change any of:
        new_date  : 'YYYY-MM-DD'  (keep current date if empty)
        new_time  : 'HH:MM'       (keep current time if empty)
        new_title : new name      (keep current title if empty)

    How it keeps the event's length: we first READ the current event to learn
    its start and end, work out how long it is, and apply that same length to
    the new start. So moving a 90-minute meeting stays 90 minutes.
    """
    svc = _service()

    # 1. Read the current event so we know its present date/time/length.
    existing = svc.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()

    # Timed events store start/end under 'dateTime' (an ISO string with an
    # offset, e.g. '2026-06-16T15:00:00-04:00'). Convert both into Eastern
    # wall-clock so we can read off the current date and time cleanly.
    eastern = ZoneInfo(TZ_NAME)
    start_dt = datetime.fromisoformat(existing["start"]["dateTime"]).astimezone(eastern)
    end_dt = datetime.fromisoformat(existing["end"]["dateTime"]).astimezone(eastern)
    duration = end_dt - start_dt  # how long the event currently is

    # 2. Decide the new date and time: use what was passed in, else keep current.
    date_str = (new_date or start_dt.strftime("%Y-%m-%d")).strip()
    time_str = (new_time or start_dt.strftime("%H:%M")).strip()

    # 3. Build the new start/end as LOCAL wall-clock (same trick as create_event:
    #    hand Google the plain local time plus the timezone NAME, no UTC math).
    new_start_local = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    new_end_local = new_start_local + duration

    body = {
        "start": {"dateTime": new_start_local.isoformat(), "timeZone": TZ_NAME},
        "end": {"dateTime": new_end_local.isoformat(), "timeZone": TZ_NAME},
    }
    if new_title.strip():
        body["summary"] = new_title.strip()

    # 4. patch() changes only the fields we send; everything else stays put.
    updated = svc.events().patch(calendarId=CALENDAR_ID, eventId=event_id, body=body).execute()

    pretty_time = new_start_local.strftime("%I:%M %p").lstrip("0")  # '4:00 PM'
    confirmed_when = new_start_local.strftime("%a %b %d, ") + pretty_time + " ET"

    return {
        "link": updated.get("htmlLink", ""),
        "confirmed_when": confirmed_when,
        "id": updated.get("id", event_id),
    }


def list_events_for_day(date_str: str = "") -> list:
    """
    Return the events on ONE day, in time order, as a list of dicts:
        [{"time_label": "9:00 AM", "title": "Standup", "all_day": False}, ...]

    date_str: 'YYYY-MM-DD'. Empty string means TODAY (in Eastern).

    This is what the morning brief reads. We ask Google for everything between
    midnight and midnight Eastern on that day. singleEvents=True expands
    repeating events into individual ones; orderBy='startTime' sorts them.
    """
    eastern = ZoneInfo(TZ_NAME)
    if date_str:
        day = datetime.strptime(date_str, "%Y-%m-%d")
        day = day.replace(tzinfo=eastern)
    else:
        now = datetime.now(eastern)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    start_of_day = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    result = _service().events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    out = []
    for item in result.get("items", []):
        start = item.get("start", {})
        title = item.get("summary", "(no title)")
        if "dateTime" in start:
            # A timed event. Convert to Eastern and make a short label.
            dt = datetime.fromisoformat(start["dateTime"]).astimezone(eastern)
            label = dt.strftime("%I:%M %p").lstrip("0")  # '9:00 AM'
            out.append({"time_label": label, "title": title, "all_day": False})
        else:
            # An all-day event (start has 'date', no clock time).
            out.append({"time_label": "all day", "title": title, "all_day": True})
    return out


# ---------------------------------------------------------------------------
# Smoke test: run `py gcal.py` to create a test event, then MOVE it, proving
# both create and update work. Same event id throughout - no duplicate.
# Also prints today's events so you can see list_events_for_day at work.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    tomorrow = (datetime.now(ZoneInfo(TZ_NAME)) + timedelta(days=1)).strftime("%Y-%m-%d")

    created = create_event("JARVIS test event (safe to delete)", tomorrow, "15:00")
    print("Created a test event:")
    print("  When :", created["confirmed_when"], "  (expect 3:00 PM ET tomorrow)")
    print("  Id   :", created["id"])
    print("  Link :", created["link"])

    moved = update_event(created["id"], new_time="16:00")
    print("\nMoved the SAME event to a new time:")
    print("  When :", moved["confirmed_when"], "  (expect 4:00 PM ET tomorrow)")
    print("  Id   :", moved["id"], " (should match the id above)")
    print("  Link :", moved["link"])

    print("\nCheck your calendar - there should be ONE event at 4:00 PM ET tomorrow,")
    print("not two. Same id before and after means we edited it, not duplicated it.")
    print("Delete the test event whenever you like.")

    print("\nToday's events (via list_events_for_day):")
    todays = list_events_for_day()
    if not todays:
        print("  (nothing on the calendar today)")
    for e in todays:
        print(f"  {e['time_label']}  {e['title']}")
