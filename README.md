# 🎵 Telegram Music Bot

Play music in Telegram Group Voice Chats! Supports YouTube search and direct URLs.

## Commands

| Command | Description |
|---------|-------------|
| `/play <song or URL>` | Search YouTube & play in voice chat |
| `/skip` | Skip current track |
| `/stop` | Stop music & leave voice chat |
| `/queue` | Show current queue |
| `/help` | Show help |

---

## ⚙️ Setup Guide (Step by Step)

### Step 1 — Get your Telegram API credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click **"API Development Tools"**
4. Create a new app → copy **`API_ID`** and **`API_HASH`**

### Step 2 — Create your Bot

1. Open Telegram → search **@BotFather**
2. Send `/newbot` → follow instructions
3. Copy the **`BOT_TOKEN`**

### Step 3 — Deploy to Railway (Free)

1. Push this project to a **GitHub repository**
   ```
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

2. Go to https://railway.app → **Sign up free** (with GitHub)

3. Click **"New Project"** → **"Deploy from GitHub repo"** → select your repo

4. Go to your project → **Variables** tab → add these:
   ```
   API_ID      = (from Step 1)
   API_HASH    = (from Step 1)
   BOT_TOKEN   = (from Step 2)
   ```

5. Railway will auto-build using the Dockerfile. Your bot will be live in ~2 minutes!

---

## 🎤 How to Use in a Group

1. Add your bot to a Telegram group
2. **Start a Voice Chat** in the group (Group info → Start Voice Chat)
3. Send `/play <song name>` — the bot joins and plays!

---

## 🛠 Tech Stack

- **pyrogram** — Telegram client
- **py-tgcalls** — Voice chat streaming
- **yt-dlp** — YouTube audio download
- **ffmpeg** — Audio processing

---

## ⚠️ Notes

- The bot needs an **active Voice Chat** in the group to join
- Free Railway plan gives ~500 hours/month (enough for a personal bot)
- Add the bot as **admin** in the group for best results
