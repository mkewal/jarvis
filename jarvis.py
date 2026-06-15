"""
JARVIS - Milestone 4 (complete): "Add to-dos + memory."

What changed from Milestone 3:
  - To-dos now SAVE to todos.json and can be listed back (part 1).
  - The bot now has a short MEMORY (part 2), kept in memory.json:
      * the last ~16 messages, fed back to Claude so follow-ups have context.
      * the last 5 events you created, shown to Claude as a numbered list, so
        "actually make it 4pm" EDITS the right calendar event instead of
        creating a duplicate.

  Claude picks one of FIVE buttons per message:
      create_event, create_todo, list_todos, update_event, unclear.

  'undo' still removes the last event added this session.
"""

import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from anthropic import Anthropic

# APScheduler runs the 6am brief on a background timer inside this same process.
# We import it optionally: if it isn't installed yet, the bot still runs (just
# without the scheduled brief) so you can set things up at your own pace.
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    HAVE_SCHEDULER = True
except ImportError:
    HAVE_SCHEDULER = False

# Our own helpers, right next to this file.
from gcal import create_event, delete_event, update_event, list_events_for_day
import store

# ---------------------------------------------------------------------------
# 1. Load secrets from .env (never hard-code these in the file)
# ---------------------------------------------------------------------------
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "paste-your-token-here":
    raise SystemExit("No Telegram token found in .env (TELEGRAM_BOT_TOKEN).")
if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "paste-your-key-here":
    raise SystemExit("No Anthropic key found in .env (ANTHROPIC_API_KEY).")

API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Your own Telegram chat id, so the unattended 9am job knows where to send the
# brief (there's no incoming message to reply to at 9am). Optional: if it's not
# set, the bot still runs and the on-demand 'brief' command still works.
MY_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

claude = Anthropic()  # reads ANTHROPIC_API_KEY from the environment

MY_TZ = ZoneInfo("America/New_York")
MODEL = "claude-haiku-4-5-20251001"

UNDO_WORDS = {"undo", "undo that", "delete that", "cancel that", "remove that", "nvm"}


def is_authorized(chat_id) -> bool:
    """Milestone 6 security: only respond to YOU.

    Telegram bots are reachable by anyone who finds the handle, so we compare
    each sender's chat id to TELEGRAM_CHAT_ID from .env. If that isn't set we
    can't lock the bot, so we allow everything (and warn loudly at startup)
    rather than silently bricking."""
    if not MY_CHAT_ID:
        return True
    return str(chat_id).strip() == str(MY_CHAT_ID).strip()

# Words that mean "give me today's rundown now" (the on-demand morning brief).
BRIEF_WORDS = {"brief", "today", "morning brief", "my day", "what's today",
               "whats today", "what's on today", "whats on today"}


# ---------------------------------------------------------------------------
# 2. The five "buttons" we let Claude press (the tools)
# ---------------------------------------------------------------------------
CREATE_EVENT_TOOL = {
    "name": "create_event",
    "description": (
        "Use when the user describes something at a specific DATE and TIME, e.g. "
        "'dentist Tuesday 3pm'. Writes a NEW calendar event. Do NOT use this to "
        "change an event that already exists - use update_event for that."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short clean title, e.g. 'Dentist'."},
            "date": {
                "type": "string",
                "description": "Resolved absolute date as YYYY-MM-DD (resolve relative days to the NEXT upcoming match).",
            },
            "time": {"type": "string", "description": "24-hour HH:MM, e.g. '15:00'."},
            "note": {"type": "string", "description": "Optional one-line note; empty string if none."},
        },
        "required": ["title", "date", "time", "note"],
    },
}

CREATE_TODO_TOOL = {
    "name": "create_todo",
    "description": (
        "Use for a task with NO specific time, e.g. 'email the housing office'. "
        "Saves it to the user's to-do list."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short clean task title."},
            "due": {"type": "string", "description": "Optional due date YYYY-MM-DD if clearly implied; else empty string."},
            "note": {"type": "string", "description": "Optional one-line note; empty string if none."},
        },
        "required": ["title", "due", "note"],
    },
}

LIST_TODOS_TOOL = {
    "name": "list_todos",
    "description": "Use when the user asks to SEE their tasks, e.g. 'what's on my list?'. Takes no input.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

UPDATE_EVENT_TOOL = {
    "name": "update_event",
    "description": (
        "Use when the user wants to CHANGE an event they recently created, e.g. "
        "'actually make it 4pm', 'move the dentist to Wednesday', 'rename it to X'. "
        "The system prompt lists their recent events with NUMBERS - set item_number "
        "to the one they mean (read the conversation to resolve 'it'/'that'). "
        "Fill only the fields that change; leave the rest as empty strings."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "item_number": {
                "type": "integer",
                "description": "Which recent event to change, using the number from the list in the system prompt.",
            },
            "new_date": {"type": "string", "description": "New date YYYY-MM-DD, or empty string to keep current."},
            "new_time": {"type": "string", "description": "New time HH:MM, or empty string to keep current."},
            "new_title": {"type": "string", "description": "New title, or empty string to keep current."},
            "note": {"type": "string", "description": "Optional one-line note; empty string if none."},
        },
        "required": ["item_number", "new_date", "new_time", "new_title", "note"],
    },
}

CANCEL_EVENT_TOOL = {
    "name": "cancel_event",
    "description": (
        "Use when the user wants to DELETE / CANCEL / REMOVE an existing event, e.g. "
        "'delete the dentist', 'cancel my 3pm', 'remove the lunch with Priya'. "
        "The system prompt lists their recent events with NUMBERS - set item_number "
        "to the one they mean (read the conversation to resolve 'it'/'that')."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "item_number": {
                "type": "integer",
                "description": "Which recent event to delete, using the number from the list in the system prompt.",
            },
            "note": {"type": "string", "description": "Optional one-line note; empty string if none."},
        },
        "required": ["item_number", "note"],
    },
}

UNCLEAR_TOOL = {
    "name": "unclear",
    "description": "Use ONLY when you genuinely cannot tell what the user wants.",
    "input_schema": {
        "type": "object",
        "properties": {
            "read_as": {"type": "string", "description": "Your best guess at what they said."},
            "note": {"type": "string", "description": "What is unclear."},
        },
        "required": ["read_as", "note"],
    },
}

ALL_TOOLS = [CREATE_EVENT_TOOL, CREATE_TODO_TOOL, LIST_TODOS_TOOL, UPDATE_EVENT_TOOL, CANCEL_EVENT_TOOL, UNCLEAR_TOOL]


def pretty_datetime(date_str: str, time_str: str) -> str:
    """Turn '2026-06-16' + '15:00' into 'Tue Jun 16, 3:00 PM ET'."""
    if not date_str:
        return ""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        date_part = d.strftime("%a %b %d").replace(" 0", " ")
    except ValueError:
        return date_str
    if time_str:
        try:
            t = datetime.strptime(time_str, "%H:%M")
            time_part = t.strftime("%I:%M %p").lstrip("0")
        except ValueError:
            time_part = time_str
        return f"{date_part}, {time_part} ET"
    return f"{date_part}"


def parse_message(text: str, chat_id) -> dict:
    """Send the user's text (plus recent context) to Claude.

    Returns {'tool': name, 'input': {...}}.
    """
    now = datetime.now(MY_TZ)
    today_context = now.strftime("%A, %B %d, %Y")

    # Build the numbered list of recent events so Claude can target an edit.
    recents = store.get_recent_events(chat_id)
    if recents:
        lines = ["The user's recent events (use the NUMBER as item_number; higher number = more recently added):"]
        for i, e in enumerate(recents, start=1):
            lines.append(f"  {i}. {e['title']} - {pretty_datetime(e['date'], e['time'])}")
        recent_block = "\n".join(lines)
    else:
        recent_block = "The user has no recent events on file yet (nothing to edit)."

    system_prompt = (
        "You are JARVIS, a personal scheduling assistant. For each message, call "
        "exactly ONE tool.\n\n"
        f"The current date and time is: {today_context}, timezone America/New_York (Eastern).\n"
        "Resolve relative days ('today','tomorrow','Tuesday','next week') to the NEXT "
        "upcoming matching date as YYYY-MM-DD.\n"
        "A date AND time => create_event. A task with no time => create_todo. A request "
        "to see tasks => list_todos. A request to CHANGE an existing event => update_event. "
        "A request to DELETE/CANCEL an existing event => cancel_event. "
        "Use unclear only as a last resort.\n\n"
        "Use the conversation history to understand follow-ups: 'it'/'that'/'the dentist' "
        "usually refer to a recent event below.\n\n"
        f"{recent_block}"
    )

    # Feed back the rolling conversation so follow-ups have context. We make sure
    # the history starts with one of the user's messages (the API requires that).
    mem = store.get_memory(chat_id)
    history = [{"role": m["role"], "content": m["text"]} for m in mem["messages"]]
    while history and history[0]["role"] != "user":
        history.pop(0)
    messages = history + [{"role": "user", "content": text}]

    response = claude.messages.create(
        model=MODEL,
        max_tokens=400,
        system=system_prompt,
        tools=ALL_TOOLS,
        tool_choice={"type": "any"},  # force one tool, Claude's choice
        messages=messages,
    )

    for block in response.content:
        if block.type == "tool_use":
            return {"tool": block.name, "input": block.input}
    return {"tool": "unclear", "input": {"read_as": text, "note": "Could not parse."}}


# ---------------------------------------------------------------------------
# 3. Handlers: each turns a parsed tool call into action + a reply
# ---------------------------------------------------------------------------
def _handle_create_event(data: dict, chat_id) -> str:
    title = (data.get("title") or "").strip() or "(untitled)"
    date_str = (data.get("date") or "").strip()
    time_str = (data.get("time") or "").strip()
    note = (data.get("note") or "").strip()

    if not date_str or not time_str:
        when = pretty_datetime(date_str, time_str)
        reply = (
            "That looks like an event, but I couldn't pin down both a date and a time.\n"
            f"- I read: {title}" + (f"\n- {when}" if when else "")
            + "\nTry something like 'dentist Tuesday 3pm'."
        )
        if note:
            reply += f"\n(note: {note})"
        return reply

    try:
        result = create_event(title, date_str, time_str)
    except Exception as e:
        print("   CALENDAR ERROR:", e)
        return f"I understood the event, but couldn't write it to your calendar: {e}"

    # Remember it so a later 'make it 4pm' can edit exactly this one.
    store.add_recent_event(chat_id, result["id"], title, date_str, time_str)
    # And remember it as the single 'last event' so 'undo' can remove it later,
    # even after a restart (this is saved in memory.json).
    store.set_last_event(chat_id, result["id"], title)

    reply = (
        "Added to your calendar\n"
        f"- {title}\n"
        f"- {result['confirmed_when']}\n"
        f"{result['link']}\n"
        "Wrong? Reply 'undo' to remove it."
    )
    if note:
        reply += f"\n(note: {note})"
    return reply


def _handle_create_todo(data: dict, chat_id) -> str:
    title = (data.get("title") or "").strip() or "(untitled)"
    due = (data.get("due") or "").strip()
    note = (data.get("note") or "").strip()

    saved = store.add_todo(chat_id, title, due)
    open_count = len(store.list_todos(chat_id))

    reply = f"Added to your list: {saved['title']}"
    if due:
        reply += f"\n- Due: {pretty_datetime(due, '')}"
    reply += f"\nYou now have {open_count} open to-do(s). Say 'what's on my list' to see them."
    if note:
        reply += f"\n(note: {note})"
    return reply


def _handle_list_todos(data: dict, chat_id) -> str:
    todos = store.list_todos(chat_id)
    if not todos:
        return "Your to-do list is empty."
    lines = ["Your open to-dos:"]
    for t in todos:
        line = f"  {t['id']}. {t['title']}"
        if t.get("due"):
            line += f"  (due {pretty_datetime(t['due'], '')})"
        lines.append(line)
    return "\n".join(lines)


def _handle_update_event(data: dict, chat_id) -> str:
    recents = store.get_recent_events(chat_id)
    if not recents:
        return "I don't have a recent event on file to change. Add one first, e.g. 'dentist Tuesday 3pm'."

    try:
        idx = int(data.get("item_number")) - 1
    except (TypeError, ValueError):
        idx = -1
    if idx < 0 or idx >= len(recents):
        return "I wasn't sure which event you meant. Try naming it, e.g. 'move the dentist to 4pm'."

    target = recents[idx]
    new_date = (data.get("new_date") or "").strip()
    new_time = (data.get("new_time") or "").strip()
    new_title = (data.get("new_title") or "").strip()
    note = (data.get("note") or "").strip()

    if not (new_date or new_time or new_title):
        return "Got that you want to change something, but not what to. Try 'make it 4pm' or 'move it to Wednesday'."

    try:
        result = update_event(target["cal_id"], new_date, new_time, new_title)
    except Exception as e:
        print("   UPDATE ERROR:", e)
        return f"I understood the change, but couldn't update your calendar: {e}"

    # Update our stored copy so a SECOND follow-up edits from the new state.
    store.update_recent_event(chat_id, idx, new_date, new_time, new_title)
    final_title = new_title or target["title"]
    store.set_last_event(chat_id, target["cal_id"], final_title)

    reply = (
        "Updated on your calendar\n"
        f"- {final_title}\n"
        f"- {result['confirmed_when']}\n"
        f"{result['link']}\n"
        "Wrong? Reply 'undo' to remove it."
    )
    if note:
        reply += f"\n(note: {note})"
    return reply


def _handle_cancel_event(data: dict, chat_id) -> str:
    recents = store.get_recent_events(chat_id)
    if not recents:
        return "I don't have a recent event on file to cancel. (I can only delete ones I recently added.)"

    try:
        idx = int(data.get("item_number")) - 1
    except (TypeError, ValueError):
        idx = -1
    if idx < 0 or idx >= len(recents):
        return "I wasn't sure which event you meant. Try naming it, e.g. 'delete the dentist'."

    target = recents[idx]
    note = (data.get("note") or "").strip()

    try:
        delete_event(target["cal_id"])
    except Exception as e:
        print("   CANCEL ERROR:", e)
        return f"I understood you want to delete '{target['title']}', but couldn't remove it: {e}"

    # Drop it from our recent list, and clear undo if it pointed here.
    store.remove_recent_event(chat_id, idx)
    last = store.get_last_event(chat_id)
    if last and last.get("cal_id") == target["cal_id"]:
        store.clear_last_event(chat_id)

    reply = (
        "Removed from your calendar\n"
        f"- {target['title']}\n"
        f"- was {pretty_datetime(target['date'], target['time'])}"
    )
    if note:
        reply += f"\n(note: {note})"
    return reply


def _handle_unclear(data: dict, chat_id) -> str:
    read_as = (data.get("read_as") or "").strip()
    note = (data.get("note") or "").strip()
    reply = "Not sure I got that."
    if read_as:
        reply += f"\n- I read: {read_as}"
    if note:
        reply += f"\n- {note}"
    return reply


def act_on_item(parsed: dict, chat_id) -> str:
    tool = parsed.get("tool", "unclear")
    data = parsed.get("input", {}) or {}
    if tool == "create_event":
        return _handle_create_event(data, chat_id)
    if tool == "create_todo":
        return _handle_create_todo(data, chat_id)
    if tool == "list_todos":
        return _handle_list_todos(data, chat_id)
    if tool == "update_event":
        return _handle_update_event(data, chat_id)
    if tool == "cancel_event":
        return _handle_cancel_event(data, chat_id)
    return _handle_unclear(data, chat_id)


# ---------------------------------------------------------------------------
# 3b. The morning brief: today's events + open to-dos, as one short message
# ---------------------------------------------------------------------------
def build_brief(chat_id) -> str:
    """Assemble the day's rundown. Used by the 'brief' command AND the 6am job."""
    today = datetime.now(MY_TZ)
    header = "Good morning. " + today.strftime("%A %b %d").replace(" 0", " ")

    try:
        events = list_events_for_day()  # today's calendar events, time-ordered
    except Exception as e:
        print("   BRIEF CALENDAR ERROR:", e)
        events = None

    todos = store.list_todos(chat_id)

    lines = [header, ""]
    if events is None:
        lines.append("(Couldn't reach your calendar just now.)")
    elif events:
        for e in events:
            lines.append(f"- {e['time_label']}  {e['title']}")
    else:
        lines.append("- No events on the calendar today.")

    lines.append("")
    if todos:
        lines.append("To-do:")
        for t in todos:
            lines.append(f"- {t['title']}")
    else:
        lines.append("To-do: nothing open.")

    return "\n".join(lines)


def send_morning_brief():
    """Build today's brief and PUSH it to you (used by the 9am scheduled job
    and by 'py jarvis.py testbrief'). Needs TELEGRAM_CHAT_ID in .env."""
    if not MY_CHAT_ID:
        print("No TELEGRAM_CHAT_ID set - can't send the brief. Add it to .env.")
        return
    try:
        send_message(MY_CHAT_ID, build_brief(MY_CHAT_ID))
        print("Sent the morning brief.")
    except Exception as e:
        print("Morning brief error:", e)


# ---------------------------------------------------------------------------
# 4. Telegram plumbing (unchanged)
# ---------------------------------------------------------------------------
def get_updates(offset=None):
    params = {"timeout": 30, "offset": offset}
    r = requests.get(f"{API}/getUpdates", params=params, timeout=40)
    return r.json()["result"]


def send_message(chat_id, text):
    requests.post(f"{API}/sendMessage", data={"chat_id": chat_id, "text": text})


# ---------------------------------------------------------------------------
# 5. The main loop
# ---------------------------------------------------------------------------
def start_scheduler():
    """Start the background 9am-brief timer, if possible. Returns the scheduler
    (so we can stop it cleanly) or None if it isn't running."""
    if not HAVE_SCHEDULER:
        print("apscheduler not installed - 9am brief is OFF. (pip install apscheduler to enable.)")
        return None
    if not MY_CHAT_ID:
        print("No TELEGRAM_CHAT_ID in .env - 9am brief is OFF. (The 'brief' command still works.)")
        return None

    scheduler = BackgroundScheduler(timezone="America/New_York")
    scheduler.add_job(send_morning_brief, "cron", hour=9, minute=0)
    scheduler.start()
    print("9am brief is ON (sends to your chat each day at 9:00 AM Eastern).")
    print("Note: this only fires while the bot is actually running at 9am.")
    print("It runs unattended for real once we deploy it (Milestone 7).")
    return scheduler


def main():
    print("JARVIS (Milestone 6 - locked down) is running.")
    print("Try 'dentist Tuesday 3pm', then 'actually make it 4pm'. Or 'brief' for today's rundown.")
    print("Press Ctrl+C to stop.\n")

    if MY_CHAT_ID:
        print(f"Locked to your chat id ({MY_CHAT_ID}) - messages from anyone else are ignored.")
    else:
        print("WARNING: TELEGRAM_CHAT_ID is not set in .env - the bot will reply to ANYONE.")
        print("         Add your chat id to .env to lock it down (Milestone 6).")

    scheduler = start_scheduler()
    offset = None
    while True:
        try:
            for update in get_updates(offset):
                offset = update["update_id"] + 1
                message = update.get("message")
                if not message or "text" not in message:
                    continue

                chat_id = message["chat"]["id"]
                text = message["text"]
                print(f"Received from chat_id {chat_id}: {text}")

                # Security gate: ignore anyone who isn't you. No reply, no
                # calendar write, nothing saved to memory.
                if not is_authorized(chat_id):
                    print(f"   IGNORED - chat_id {chat_id} is not authorized. No reply sent.")
                    continue

                # Decide the reply (a few commands are handled without Claude).
                if text.strip().lower() in BRIEF_WORDS:
                    reply = build_brief(chat_id)
                elif text.strip().lower() in UNDO_WORDS:
                    last = store.get_last_event(chat_id)
                    if last:
                        try:
                            delete_event(last["cal_id"])
                            # Keep both stores in sync: forget the last-event note
                            # and drop it from the editable recent list.
                            store.remove_recent_event_by_calid(chat_id, last["cal_id"])
                            store.clear_last_event(chat_id)
                            reply = f"Removed '{last['title']}' from your calendar."
                        except Exception as e:
                            print("   UNDO ERROR:", e)
                            reply = f"Couldn't remove it: {e}"
                    else:
                        reply = "Nothing to undo - I haven't added an event recently."
                else:
                    try:
                        parsed = parse_message(text, chat_id)
                        print("   parsed ->", parsed)
                        reply = act_on_item(parsed, chat_id)
                    except Exception as e:
                        reply = f"My brain hit an error: {e}"
                        print("   ERROR:", e)

                send_message(chat_id, reply)

                # Record BOTH sides of this turn in memory, as a pair, so the
                # rolling history stays in clean user/assistant order.
                store.append_message(chat_id, "user", text)
                store.append_message(chat_id, "assistant", reply)

        except KeyboardInterrupt:
            print("\nStopped. See you next time.")
            if scheduler:
                scheduler.shutdown(wait=False)
            break
        except Exception as e:
            print("Minor hiccup, retrying in 3s:", e)
            time.sleep(3)


if __name__ == "__main__":
    # `py jarvis.py testbrief` sends the brief to you immediately, so you can
    # test the unattended 9am path without waiting until 9am.
    if len(sys.argv) > 1 and sys.argv[1] == "testbrief":
        send_morning_brief()
    else:
        main()
