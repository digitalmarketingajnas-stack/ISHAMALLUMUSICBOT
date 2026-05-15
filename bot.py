import asyncio
import os
import re
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream import AudioParameters
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType, ChatMemberStatus
import yt_dlp

# ── Config ────────────────────────────────────────────────────────────────────
API_ID    = int(os.environ["API_ID"])
API_HASH  = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID  = int(os.environ["OWNER_ID"])   # Your Telegram numeric user ID

# ── Clients ───────────────────────────────────────────────────────────────────
app        = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls  = PyTgCalls(app)

# ── Queue: { chat_id: [{"title": str, "url": str}, ...] } ─────────────────────
queues: dict[int, list[dict]] = {}

# ── Helpers ───────────────────────────────────────────────────────────────────
YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "128",
    }],
    "outtmpl": "/tmp/%(id)s.%(ext)s",
}

def search_and_get_url(query: str) -> tuple[str, str]:
    """Returns (title, audio_path)"""
    is_url = re.match(r"https?://", query)
    opts = YDL_OPTS.copy()
    with yt_dlp.YoutubeDL(opts) as ydl:
        if is_url:
            info = ydl.extract_info(query, download=True)
        else:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            info = info["entries"][0]
        title = info.get("title", "Unknown")
        path  = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
        return title, path

async def play_next(chat_id: int):
    if not queues.get(chat_id):
        await pytgcalls.leave_group_call(chat_id)
        return
    track = queues[chat_id][0]
    await pytgcalls.change_stream(
        chat_id,
        AudioPiped(track["path"], AudioParameters.from_quality("high")),
    )

# ── Commands ──────────────────────────────────────────────────────────────────
@app.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    is_owner = msg.from_user and msg.from_user.id == OWNER_ID
    owner_section = (
        "\n\n**👑 Owner Commands:**\n"
        "/broadcast `<message>` — Send message to all groups & channels\n"
        "/listchats — List all chats where bot is admin"
    ) if is_owner else ""
    await msg.reply_text(
        "🎵 **Music Bot** — Play music in Voice Chats!\n\n"
        "**Commands:**\n"
        "/play `<song name or YouTube URL>` — Add to queue & play\n"
        "/skip — Skip current track\n"
        "/stop — Stop & leave VC\n"
        "/queue — Show queue\n"
        "/help — Show this message"
        + owner_section
    )

@app.on_message(filters.command("help"))
async def cmd_help(_, msg: Message):
    await cmd_start(_, msg)

@app.on_message(filters.command("play"))
async def cmd_play(_, msg: Message):
    chat_id = msg.chat.id
    query   = " ".join(msg.command[1:])

    if not query:
        await msg.reply_text("❌ Usage: `/play <song name or URL>`")
        return

    status_msg = await msg.reply_text("🔍 Searching...")

    try:
        title, path = await asyncio.get_event_loop().run_in_executor(
            None, search_and_get_url, query
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: `{e}`")
        return

    track = {"title": title, "path": path}

    if chat_id not in queues:
        queues[chat_id] = []

    queues[chat_id].append(track)

    if len(queues[chat_id]) == 1:
        # First track → join and play
        try:
            await pytgcalls.join_group_call(
                chat_id,
                AudioPiped(path, AudioParameters.from_quality("high")),
            )
            await status_msg.edit_text(f"▶️ Now playing: **{title}**")
        except Exception as e:
            await status_msg.edit_text(f"❌ Could not join voice chat: `{e}`\nMake sure a Voice Chat is active in this group.")
            queues[chat_id].pop()
    else:
        pos = len(queues[chat_id])
        await status_msg.edit_text(f"✅ **{title}** added to queue (position #{pos})")

@app.on_message(filters.command("skip"))
async def cmd_skip(_, msg: Message):
    chat_id = msg.chat.id
    if not queues.get(chat_id):
        await msg.reply_text("❌ Queue is empty.")
        return
    queues[chat_id].pop(0)
    if queues[chat_id]:
        await play_next(chat_id)
        await msg.reply_text(f"⏭️ Skipped. Now playing: **{queues[chat_id][0]['title']}**")
    else:
        await pytgcalls.leave_group_call(chat_id)
        await msg.reply_text("⏹️ Queue ended. Left voice chat.")

@app.on_message(filters.command("stop"))
async def cmd_stop(_, msg: Message):
    chat_id = msg.chat.id
    queues.pop(chat_id, None)
    try:
        await pytgcalls.leave_group_call(chat_id)
    except Exception:
        pass
    await msg.reply_text("⏹️ Stopped and left voice chat.")

@app.on_message(filters.command("queue"))
async def cmd_queue(_, msg: Message):
    chat_id = msg.chat.id
    q = queues.get(chat_id, [])
    if not q:
        await msg.reply_text("📭 Queue is empty.")
        return
    lines = [f"{'▶️' if i == 0 else f'{i}.'} {t['title']}" for i, t in enumerate(q)]
    await msg.reply_text("🎶 **Queue:**\n" + "\n".join(lines))

# ── Owner-only: list admin chats ─────────────────────────────────────────────
@app.on_message(filters.command("listchats") & filters.private)
async def cmd_listchats(_, msg: Message):
    if msg.from_user.id != OWNER_ID:
        await msg.reply_text("❌ This command is only for the bot owner.")
        return

    status_msg = await msg.reply_text("🔍 Scanning chats...")
    admin_chats = []

    async for dialog in app.get_dialogs():
        chat = dialog.chat
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
            continue
        try:
            me = await app.get_chat_member(chat.id, (await app.get_me()).id)
            if me.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                kind = "📢 Channel" if chat.type == ChatType.CHANNEL else "👥 Group"
                admin_chats.append(f"{kind} — **{chat.title}** (`{chat.id}`)")
        except Exception:
            continue

    if not admin_chats:
        await status_msg.edit_text("😕 Bot is not an admin in any group or channel yet.")
        return

    chunks = []
    current = f"✅ **Bot is admin in {len(admin_chats)} chat(s):**\n\n"
    for line in admin_chats:
        if len(current) + len(line) > 4000:
            chunks.append(current)
            current = ""
        current += line + "\n"
    chunks.append(current)

    await status_msg.edit_text(chunks[0])
    for chunk in chunks[1:]:
        await msg.reply_text(chunk)


# ── Owner-only: broadcast ─────────────────────────────────────────────────────
@app.on_message(filters.command("broadcast") & filters.private)
async def cmd_broadcast(_, msg: Message):
    if msg.from_user.id != OWNER_ID:
        await msg.reply_text("❌ This command is only for the bot owner.")
        return

    # Support text, or forwarded/replied message
    broadcast_text = " ".join(msg.command[1:])
    reply = msg.reply_to_message

    if not broadcast_text and not reply:
        await msg.reply_text(
            "❌ Usage:\n"
            "• `/broadcast <your message>` — Send text\n"
            "• Reply to any message with `/broadcast` — Forward that message"
        )
        return

    status_msg = await msg.reply_text("📡 Broadcasting...")

    sent = 0
    failed = 0
    me_id = (await app.get_me()).id

    async for dialog in app.get_dialogs():
        chat = dialog.chat
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
            continue
        try:
            member = await app.get_chat_member(chat.id, me_id)
            if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                continue
            if reply:
                await reply.forward(chat.id)
            else:
                await app.send_message(chat.id, broadcast_text)
            sent += 1
            await asyncio.sleep(0.3)   # avoid flood
        except Exception as e:
            print(f"Broadcast failed for {chat.id}: {e}")
            failed += 1

    await status_msg.edit_text(
        f"📣 **Broadcast complete!**\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


# ── Stream ended → auto-play next ────────────────────────────────────────────
@pytgcalls.on_stream_end()
async def on_stream_end(_, update):
    chat_id = update.chat_id
    if queues.get(chat_id):
        queues[chat_id].pop(0)
    await play_next(chat_id)

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    await app.start()
    await pytgcalls.start()
    print("✅ Bot is running...")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
