# Paste this into a new chat to start Milestone 2

---

I'm building JARVIS, a Telegram scheduling assistant, as a learning project. The full spec is at `Claude cowork/JARVIS_Spec.md` — please read it first for full context.

**About me:** I'm not an engineer. Walk me through everything step by step, in plain English, and don't assume coding knowledge. I'm on a Windows laptop. I learn by doing one runnable step at a time.

**Where things stand — Milestone 1 is done and working.** I have a `jarvis` folder (in `Claude cowork/jarvis`) containing:
- `echo_bot.py` — a working Telegram echo bot using `requests` + long polling. It reads my bot token from `.env`, listens for my messages, and texts them back. It also prints my chat_id to the console.
- `.env` — holds `TELEGRAM_BOT_TOKEN` (already filled in with my real token; keep it out of any code or chat).
- `requirements.txt` — currently lists `requests` and `python-dotenv`.
- I've got Python installed and working, and I successfully texted the bot and got echoes back.

**What I want to build now — Milestone 2: "Add a brain."** Per the spec's build sequence, the goal is:
> Pipe my message through the Claude API and have it reply with a structured interpretation (event vs to-do, with date/time). No calendar yet — just print it (and text it back to me).

So instead of echoing "You said: X," the bot should send my message to Claude, have Claude decide whether it's a **timed event** (has a date + time) or a **to-do** (no specific time), extract the details (title, date, time), and reply to me with that structured interpretation so I can sanity-check the parsing. Still no Google Calendar yet — that's Milestone 3.

**Things I'll need help with:**
- Setting up my Anthropic API key safely (in `.env`, same as the bot token). I may already have one from the Leland AI Builder course — help me check or create one.
- Choosing how to prompt Claude so it reliably returns structured output (event vs to-do + fields).
- Handling timezones / date ambiguity sensibly — I'm in ET, moving to Philadelphia for Wharton. "Tuesday" should resolve to the next upcoming one, and JARVIS should echo back the resolved date so I can catch mistakes (the spec calls this out).

**How I like to work:** plan the approach with me first, then we build. Push back if something doesn't hold up — I don't want validation, I want it to actually work. Keep my token and API key out of any code that could get shared.

Please start by reading the spec, then walk me through Milestone 2 step by step.
