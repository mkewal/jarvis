"""
JARVIS — Milestone 1: the echo bot.

What this does: connects to your Telegram bot, listens for messages you
send it, and texts the same message right back ("You said: ...").

That's it. No AI, no calendar yet. The point is to prove two things work:
  1. Your bot token is valid.
  2. The "polling" loop (asking Telegram for new messages) works.

Everything in later milestones builds on this exact loop.
"""

import os
import time
import requests
from dotenv import load_dotenv

# Load the secret token from the .env file sitting next to this script.
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN or TOKEN == "paste-your-token-here":
    raise SystemExit(
        "No bot token found.\n"
        "Open the file named .env (in this same folder) and paste your token\n"
        "from BotFather after  TELEGRAM_BOT_TOKEN=  then save and run again."
    )

# Every Telegram API call starts with this base URL.
API = f"https://api.telegram.org/bot{TOKEN}"


def get_updates(offset=None):
    """Ask Telegram: any new messages? Waits up to 30s for one to arrive
    (this is 'long polling' — efficient, no constant hammering)."""
    params = {"timeout": 30, "offset": offset}
    response = requests.get(f"{API}/getUpdates", params=params, timeout=40)
    return response.json()["result"]


def send_message(chat_id, text):
    """Send a text message back to whoever messaged us."""
    requests.post(f"{API}/sendMessage", data={"chat_id": chat_id, "text": text})


def main():
    print("JARVIS echo bot is running.")
    print("Open Telegram, find your bot, and text it something.")
    print("Press Ctrl+C here to stop.\n")

    offset = None  # tells Telegram which messages we've already handled

    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                # Mark this message as seen so we don't process it twice.
                offset = update["update_id"] + 1

                message = update.get("message")
                if not message or "text" not in message:
                    continue  # skip non-text stuff (photos, stickers, etc.)

                chat_id = message["chat"]["id"]
                text = message["text"]

                # This printed chat_id is YOUR id — you'll need it later
                # (Milestone 6) to lock the bot to only you. Jot it down.
                print(f"Received from chat_id {chat_id}: {text}")

                send_message(chat_id, f"You said: {text}")

        except KeyboardInterrupt:
            print("\nStopped. See you next time.")
            break
        except Exception as e:
            # Network hiccup? Wait a moment and keep going.
            print("Minor hiccup, retrying in 3s:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
