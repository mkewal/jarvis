# JARVIS - Milestone 4 Kickoff Prompt

*Copy everything in the code block below into a new chat to start Milestone 4.*

---

```
I'm building JARVIS, a Telegram scheduling assistant, as a learning project. The full spec is at `Claude cowork/JARVIS_Spec.md` - read it first for full context.

About me: I'm not an engineer. Walk me through everything step by step, in plain English, no assumed coding knowledge. I'm on a Windows laptop. I learn by doing one runnable step at a time. Plan the approach with me first, then we build. Push back if something doesn't hold up - I want it to actually work, not validation. Keep my secrets (bot token, API key, service account key) out of any code or chat.

One environment note that bit us in Milestone 3: my `jarvis` folder is synced by OneDrive, and the Linux sandbox/bash mount reads stale or torn copies of these files. Do NOT trust bash (py_compile, cat, etc.) to verify my files - it invents phantom errors. Verify by running things on MY machine (e.g. `py -m py_compile ...` or running the bot), or by using the Read tool, which is authoritative.

Where things stand - Milestones 1, 2, and 3 are done and working. My `jarvis` folder (in `Claude cowork/jarvis`) contains:
- `echo_bot.py` - the original Milestone 1 echo bot (kept as a fallback).
- `jarvis.py` - the main bot. Telegram long-polling loop that pipes each message to the Claude API using tool use, classifies it as a timed EVENT or a TO-DO, resolves relative dates ("Tuesday" -> next upcoming date) in my pinned timezone America/New_York (Eastern). For an EVENT it creates a real Google Calendar event and texts back the exact date/time it wrote plus a link; reply 'undo' removes the last event. For a TO-DO it just acknowledges (nothing stored yet). It remembers only the single last event per chat, in memory, so 'undo' works - no message history yet.
- `gcal.py` - Google Calendar helper. Authenticates as a SERVICE ACCOUNT (robot identity) using `service_account.json`; my calendar is shared with that robot's email with "Make changes to events". Functions: create_event(title, date, time) and delete_event(id). Times are written with an explicit America/New_York timezone (no manual UTC math). No browser flow, no expiring token.
- `service_account.json` - the robot's private key (secret; keep out of code/chat).
- `.env` - holds TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, and GOOGLE_CALENDAR_ID (real values; keep secrets out of code/chat).
- `requirements.txt` - requests, python-dotenv, anthropic, tzdata, google-api-python-client, google-auth.

Note: the code is intentionally plain ASCII (no emoji / fancy dashes) because the OneDrive+sandbox sync was corrupting multibyte characters.

What I want to build now - Milestone 4: "Add to-dos + memory." Per the spec's build sequence:
1. A real TO-DO store. When I text a task with no time ("email the housing office"), JARVIS saves it to a small local file that survives restarts, and can list my open to-dos back to me on request. (Decide with me: a simple JSON file vs SQLite - I'd lean toward whichever is simplest to understand and inspect by hand. Also flag the spec's open question: keep to-dos purely local, or eventually sync to Google Tasks?)
2. Rolling conversation memory: keep the last 10-15 messages so follow-ups work - e.g. I add "dentist Tuesday 3pm", then text "actually make it 4pm" and JARVIS knows what "that" refers to and updates the existing calendar event. Stored in a small local file so it survives restarts.

Things I'll need help with:
- Designing the to-do store and the memory file so they're simple, inspectable, and survive restarts - and deciding whether they're one file or two.
- The trickiest part: making follow-up edits work. When I say "actually make it 4pm" or "move it to Wednesday", JARVIS needs to know which recent event/todo I mean (from memory), then UPDATE it in Google Calendar rather than create a duplicate. We'll likely need an update_event() in gcal.py and a way to remember the last item's calendar ID, not just for undo.
- Keeping the echo-back / confirmation habit so I can catch a misparse before it changes my real calendar.
- A way to ask JARVIS "what's on my list?" and have it read back open to-dos.

Please start by reading the spec and my current jarvis.py + gcal.py (use the Read tool, not bash), then plan Milestone 4 with me before we build.
```
