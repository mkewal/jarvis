"""
JARVIS - local storage helper (Milestone 4).

Two plain-text JSON files, both next to this script, both safe to open and
read by hand:

  todos.json   - your to-do list (added in part 1).
  memory.json  - the bot's short memory (added in part 2):
                   * the last ~16 messages of your conversation, so follow-ups
                     like "actually make it 4pm" have context.
                   * the last 5 events you created, each with its real calendar
                     id, so the bot can EDIT the right one instead of guessing.

Why JSON and not a database: it is just text at a tiny scale. You can read it.

The one danger with a text file is a "torn write" (the program dies mid-save and
leaves a half-written, broken file). We avoid that by writing to a temporary
file first and renaming it over the real one in a single step (os.replace), so
the real file is always either the old version or the new one - never broken.

Plain ASCII only (no emoji / fancy dashes), same as the rest of JARVIS, because
the OneDrive sync was corrupting fancy characters.
"""

import os
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

_HERE = os.path.dirname(__file__)

# Where the data files live. Defaults to the folder this script is in (the
# original behavior on your laptop). On a server (Railway) the local disk is
# WIPED on every redeploy/restart, so we set JARVIS_DATA_DIR to a persistent
# volume (e.g. /data) and the files live there instead - surviving restarts.
DATA_DIR = os.getenv("JARVIS_DATA_DIR", _HERE)
os.makedirs(DATA_DIR, exist_ok=True)  # create it if it doesn't exist yet

TODOS_FILE = os.path.join(DATA_DIR, "todos.json")
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")

MY_TZ = ZoneInfo("America/New_York")

# How much memory to keep. Messages are stored in user/assistant PAIRS, so we
# keep an EVEN number - that way the saved history always starts with one of
# your messages, which is what the Claude API expects.
MAX_MESSAGES = 16   # ~8 back-and-forths
MAX_RECENT = 5      # last 5 events we can still edit


# ---------------------------------------------------------------------------
# Low-level: read / write a whole JSON file, safely
# ---------------------------------------------------------------------------
def _read_json(path: str) -> dict:
    """Read a JSON file into a dict. Empty dict if missing or unreadable."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: str, data: dict) -> None:
    """Write a dict to a JSON file safely (temp file + atomic rename).

    OneDrive occasionally holds the file open for a moment while it syncs, so
    we retry the final swap a few times before giving up.
    """
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    for _ in range(5):
        try:
            os.replace(tmp, path)
            return
        except OSError:
            time.sleep(0.2)
    os.replace(tmp, path)  # last try; let the error surface if it still fails


# ---------------------------------------------------------------------------
# To-dos (from part 1, unchanged behavior)
# ---------------------------------------------------------------------------
def add_todo(chat_id, title: str, due: str = "") -> dict:
    """Add one to-do for this chat and return the saved to-do (a dict)."""
    data = _read_json(TODOS_FILE)
    key = str(chat_id)
    todos = data.get(key, [])
    next_id = 1 + max((t.get("id", 0) for t in todos), default=0)
    todo = {
        "id": next_id,
        "title": title.strip(),
        "due": due.strip(),
        "created": datetime.now(MY_TZ).strftime("%Y-%m-%d %H:%M"),
        "done": False,
    }
    todos.append(todo)
    data[key] = todos
    _write_json(TODOS_FILE, data)
    return todo


def list_todos(chat_id, include_done: bool = False) -> list:
    """Return this chat's to-dos. By default only the open (not done) ones."""
    todos = _read_json(TODOS_FILE).get(str(chat_id), [])
    if include_done:
        return todos
    return [t for t in todos if not t.get("done", False)]


def remove_todo(chat_id, todo_id) -> dict:
    """Delete one to-do outright by its id. Returns the removed to-do (a dict),
    or None if no to-do with that id was found."""
    data = _read_json(TODOS_FILE)
    key = str(chat_id)
    todos = data.get(key, [])
    try:
        todo_id = int(todo_id)
    except (TypeError, ValueError):
        return None
    for i, t in enumerate(todos):
        if t.get("id") == todo_id:
            removed = todos.pop(i)
            data[key] = todos
            _write_json(TODOS_FILE, data)
            return removed
    return None


# ---------------------------------------------------------------------------
# Memory (part 2): rolling messages + recent editable events
# ---------------------------------------------------------------------------
def _blank_memory() -> dict:
    return {"messages": [], "recent_events": [], "last_event": None}


def get_memory(chat_id) -> dict:
    """Return {'messages': [...], 'recent_events': [...], 'last_event': ...} for this chat."""
    entry = _read_json(MEMORY_FILE).get(str(chat_id), {})
    # Make sure all keys always exist, even for an old/blank file.
    return {
        "messages": entry.get("messages", []),
        "recent_events": entry.get("recent_events", []),
        "last_event": entry.get("last_event"),
    }


def append_message(chat_id, role: str, text: str) -> None:
    """Add one message (role = 'user' or 'assistant') to the rolling window."""
    data = _read_json(MEMORY_FILE)
    key = str(chat_id)
    entry = data.get(key, _blank_memory())
    entry.setdefault("messages", [])
    entry.setdefault("recent_events", [])
    entry["messages"].append({"role": role, "text": text})
    # Keep only the most recent MAX_MESSAGES (an even number keeps pairs intact).
    entry["messages"] = entry["messages"][-MAX_MESSAGES:]
    data[key] = entry
    _write_json(MEMORY_FILE, data)


def add_recent_event(chat_id, cal_id: str, title: str, date: str, time_str: str) -> None:
    """Remember an event we just created, so we can edit it later."""
    data = _read_json(MEMORY_FILE)
    key = str(chat_id)
    entry = data.get(key, _blank_memory())
    entry.setdefault("messages", [])
    entry.setdefault("recent_events", [])
    entry["recent_events"].append(
        {"cal_id": cal_id, "title": title, "date": date, "time": time_str}
    )
    entry["recent_events"] = entry["recent_events"][-MAX_RECENT:]
    data[key] = entry
    _write_json(MEMORY_FILE, data)


def get_recent_events(chat_id) -> list:
    """Return the list of recently created events (oldest first, newest last)."""
    return get_memory(chat_id)["recent_events"]


def update_recent_event(chat_id, index: int, new_date: str = "", new_time: str = "", new_title: str = "") -> None:
    """After an edit, update our stored copy so the NEXT follow-up sees the new
    time/date/title (e.g. '4pm' then 'no, 5pm' both work)."""
    data = _read_json(MEMORY_FILE)
    key = str(chat_id)
    entry = data.get(key)
    if not entry:
        return
    recents = entry.get("recent_events", [])
    if 0 <= index < len(recents):
        if new_date:
            recents[index]["date"] = new_date
        if new_time:
            recents[index]["time"] = new_time
        if new_title:
            recents[index]["title"] = new_title
        data[key] = entry
        _write_json(MEMORY_FILE, data)


def remove_recent_event(chat_id, index: int) -> dict:
    """Drop an event from the recent list (after we delete it from the calendar).
    Returns the removed entry, or None if the index was out of range."""
    data = _read_json(MEMORY_FILE)
    key = str(chat_id)
    entry = data.get(key)
    if not entry:
        return None
    recents = entry.get("recent_events", [])
    if 0 <= index < len(recents):
        removed = recents.pop(index)
        data[key] = entry
        _write_json(MEMORY_FILE, data)
        return removed
    return None


def remove_recent_event_by_calid(chat_id, cal_id: str) -> None:
    """Drop a recent event by its calendar id, if present. Keeps the editable
    recent list in sync after an 'undo' so you can't later try to edit an event
    that no longer exists on the calendar."""
    data = _read_json(MEMORY_FILE)
    key = str(chat_id)
    entry = data.get(key)
    if not entry:
        return
    recents = entry.get("recent_events", [])
    entry["recent_events"] = [e for e in recents if e.get("cal_id") != cal_id]
    data[key] = entry
    _write_json(MEMORY_FILE, data)


# ---------------------------------------------------------------------------
# Last event (Milestone 6): remember the single most-recently created/edited
# event so 'undo' works even after the bot restarts. This lives in memory.json,
# which survives restarts - unlike the old in-memory note that was wiped on stop.
# ---------------------------------------------------------------------------
def set_last_event(chat_id, cal_id: str, title: str) -> None:
    """Record the single most recent event we created or edited."""
    data = _read_json(MEMORY_FILE)
    key = str(chat_id)
    entry = data.get(key, _blank_memory())
    entry.setdefault("messages", [])
    entry.setdefault("recent_events", [])
    entry["last_event"] = {"cal_id": cal_id, "title": title}
    data[key] = entry
    _write_json(MEMORY_FILE, data)


def get_last_event(chat_id):
    """Return the last created/edited event {'cal_id', 'title'} or None."""
    return get_memory(chat_id).get("last_event")


def clear_last_event(chat_id) -> None:
    """Forget the last event (after it's been undone or cancelled)."""
    data = _read_json(MEMORY_FILE)
    key = str(chat_id)
    entry = data.get(key)
    if not entry:
        return
    entry["last_event"] = None
    data[key] = entry
    _write_json(MEMORY_FILE, data)


# ---------------------------------------------------------------------------
# Pending events: events read from a calendar screenshot that are waiting for
# the user to text 'confirm' before we write them to the real calendar. Lives
# in memory.json so a restart mid-confirmation doesn't lose them.
# ---------------------------------------------------------------------------
def set_pending_events(chat_id, events: list) -> None:
    """Stash a list of parsed-but-not-yet-written events for this chat."""
    data = _read_json(MEMORY_FILE)
    key = str(chat_id)
    entry = data.get(key, _blank_memory())
    entry.setdefault("messages", [])
    entry.setdefault("recent_events", [])
    entry["pending_events"] = events
    data[key] = entry
    _write_json(MEMORY_FILE, data)


def get_pending_events(chat_id) -> list:
    """Return the events awaiting confirmation (empty list if none)."""
    entry = _read_json(MEMORY_FILE).get(str(chat_id), {})
    return entry.get("pending_events", []) or []


def clear_pending_events(chat_id) -> None:
    """Forget the pending events (after they're confirmed or discarded)."""
    data = _read_json(MEMORY_FILE)
    key = str(chat_id)
    entry = data.get(key)
    if not entry:
        return
    entry["pending_events"] = []
    data[key] = entry
    _write_json(MEMORY_FILE, data)


# ---------------------------------------------------------------------------
# Smoke test: run `py store.py` to exercise BOTH stores without the bot.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    TEST = "smoke-test"

    print("To-dos:")
    add_todo(TEST, "Email the Wharton housing office")
    add_todo(TEST, "Book flights for orientation")
    for t in list_todos(TEST):
        print(f"  [{t['id']}] {t['title']}")

    print("\nMemory - messages:")
    append_message(TEST, "user", "dentist Tuesday 3pm")
    append_message(TEST, "assistant", "Added Dentist - Tue Jun 16, 3:00 PM ET")
    for m in get_memory(TEST)["messages"]:
        print(f"  {m['role']}: {m['text']}")

    print("\nMemory - recent events (before edit):")
    add_recent_event(TEST, "fake-cal-id-123", "Dentist", "2026-06-16", "15:00")
    for i, e in enumerate(get_recent_events(TEST), start=1):
        print(f"  {i}. {e['title']} {e['date']} {e['time']}")

    print("Editing event 1 to 16:00...")
    update_recent_event(TEST, 0, new_time="16:00")
    for i, e in enumerate(get_recent_events(TEST), start=1):
        print(f"  {i}. {e['title']} {e['date']} {e['time']}")

    print("\nTo-dos - removing the first one:")
    open_todos = list_todos(TEST)
    if open_todos:
        gone = remove_todo(TEST, open_todos[0]["id"])
        print(f"  removed: {gone['title'] if gone else '(nothing)'}")
        print("  remaining:")
        for t in list_todos(TEST):
            print(f"    [{t['id']}] {t['title']}")

    print(f"\nFiles:\n  {TODOS_FILE}\n  {MEMORY_FILE}")
    print("Open them in Notepad to see the raw JSON. Delete them for a clean start;")
    print("your real chat uses a number key, not 'smoke-test'.")
