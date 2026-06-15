# JARVIS — Milestone 3 Kickoff Prompt

*Copy everything in the code block below into a new chat to start Milestone 3.*

---

```
I'm building JARVIS, a Telegram scheduling assistant, as a learning project. The full spec is at `Claude cowork/JARVIS_Spec.md` — read it first for full context.

About me: I'm not an engineer. Walk me through everything step by step, in plain English, no assumed coding knowledge. I'm on a Windows laptop. I learn by doing one runnable step at a time. Plan the approach with me first, then we build. Push back if something doesn't hold up — I want it to actually work, not validation. Keep my bot token and API key out of any code or chat.

Where things stand — Milestones 1 and 2 are done and working. My `jarvis` folder (in `Claude cowork/jarvis`) contains:
- `echo_bot.py` — the original Milestone 1 echo bot (kept as a fallback).
- `jarvis.py` — Milestone 2. Telegram long-polling loop that pipes each message to the Claude API using tool use, which classifies it as a timed EVENT or a TO-DO, resolves relative dates (e.g. "Tuesday" → next upcoming date) using my pinned timezone America/New_York (Eastern — covers both NYC and Philadelphia), and texts back a structured interpretation echoing the resolved date. Nothing is written to a calendar yet — it only prints and replies.
- `.env` — holds TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY (real values; keep them out of code/chat).
- `requirements.txt` — requests, python-dotenv, anthropic, tzdata.

What I want to build now — Milestone 3: "Wire the calendar." Per the spec's build sequence: take a parsed EVENT and actually create it in my Google Calendar, then confirm back to me. To-dos stay un-stored for now (that's Milestone 4). Keep the echo-back confirmation so I can catch a misparse before it lands on my real calendar.

Things I'll need help with:
- Deciding HOW to talk to Google Calendar. Two options I want you to lay out before we build: (a) set up the Google Calendar API myself via Google Cloud Console (OAuth credentials, consent screen, token file) — more setup but more learning; or (b) use a ready-made Google Calendar connector if one's available, which skips the OAuth pain. Recommend one and tell me the tradeoff.
- If we go the Google Cloud route: walk me through the credentials/OAuth setup carefully — the spec says to budget an hour and that it's the fiddliest step.
- Making sure the event lands at the right time in Eastern Time (no UTC/timezone mistakes), and that JARVIS confirms back the exact date/time it wrote.
- Deciding what to do when I send a TO-DO (no time) during this milestone — probably just acknowledge it without storing, since the to-do store is Milestone 4.

Please start by reading the spec and my current `jarvis.py`, then plan Milestone 3 with me before we build.
```
