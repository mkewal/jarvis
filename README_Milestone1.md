# JARVIS — Milestone 1: The Echo Bot

Goal: text your bot, and it texts the same thing back. That's the whole milestone.
It proves your token works and the message loop runs. Everything else stacks on this.

You'll do five things. Take them one at a time — there's no rush, and nothing here can break your computer.

---

## Step 1 — Install Python (the language the bot is written in)

1. Go to https://www.python.org/downloads/ and click the big yellow "Download Python" button.
2. Run the installer. **Important:** on the very first screen, check the box that says
   **"Add python.exe to PATH"** at the bottom. Then click "Install Now."
3. To confirm it worked: press the Windows key, type `cmd`, hit Enter (this opens a black
   "Command Prompt" window). Type this and press Enter:

   ```
   python --version
   ```

   If you see something like `Python 3.12.4`, you're done. If it says "not recognized,"
   restart your computer and try again (the PATH change needs a reboot sometimes).

> Already had Python? Great, skip to Step 2.

---

## Step 2 — Create your bot and get its token

The "token" is a long password-like string that lets your code control your bot.

1. Open Telegram (phone or desktop). In the search bar, type **@BotFather** and open the
   account with the blue checkmark.
2. Tap **Start**, then send the message: `/newbot`
3. It asks for a **name** (anything, e.g. `JARVIS`) and then a **username** that must end
   in `bot` (e.g. `mahish_jarvis_bot`). If a username is taken, just try another.
4. BotFather replies with a line like:

   ```
   Use this token to access the HTTP API:
   8123456789:AAH...long-string...xyz
   ```

   That long string is your **token**. Copy it.

---

## Step 3 — Paste the token into the .env file

1. In this `jarvis` folder, open the file named **`.env`** (open it with Notepad — right-click → Open with → Notepad).
2. Replace `paste-your-token-here` with the token you copied, so it reads:

   ```
   TELEGRAM_BOT_TOKEN=8123456789:AAH...long-string...xyz
   ```

   No spaces, no quotes. Save and close.

> This keeps your secret token out of the code itself — a good habit you'll keep using.

---

## Step 4 — Install the two helper packages

Open Command Prompt again (Windows key → type `cmd` → Enter), then point it at this folder
and install. Copy-paste these two lines one at a time (press Enter after each):

```
cd "C:\Users\mahis\OneDrive\Desktop\Claude cowork\jarvis"
```

```
pip install -r requirements.txt
```

You'll see some text scroll by ending in "Successfully installed..." That's it.

---

## Step 5 — Run it and test

Still in Command Prompt, run:

```
python echo_bot.py
```

You should see: **"JARVIS echo bot is running."**

Now open Telegram, find your bot (search its username), tap **Start**, and text it
anything — like `hello`. Within a second or two it should reply **"You said: hello"**.

🎉 That's Milestone 1 done.

To stop the bot, click back on the Command Prompt window and press **Ctrl + C**.

---

## A bonus you'll want later

While the bot runs, the Command Prompt prints a line like:

```
Received from chat_id 6285550101: hello
```

That number is **your personal chat ID**. Write it down somewhere — Milestone 6 uses it to
lock the bot so only *you* can talk to it. No need to do anything with it now.

---

## If something goes wrong

- **"No bot token found."** → The token wasn't pasted into `.env`, or `.env` wasn't saved. Redo Step 3.
- **"python is not recognized"** → Python isn't on PATH. Reinstall (Step 1) with the PATH box checked, then reboot.
- **"pip is not recognized"** → Try `python -m pip install -r requirements.txt` instead.
- **Bot doesn't reply** → Make sure the Command Prompt still shows "running" (it must stay
  open). Confirm you tapped **Start** in the chat with your bot.

When this is working, tell me and we'll do Milestone 2 — piping your messages through Claude
so it actually understands "dentist Tuesday 3pm."
