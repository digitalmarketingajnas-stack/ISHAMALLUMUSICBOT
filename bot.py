import asyncio
import os
import re
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import AudioPiped
from pytgcalls.types.input_stream import AudioParameters
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType, ChatMemberStatus
import yt_dlp

# ── Config ────────────────────────────────────────────────────────────────────
API_ID         = int(os.environ["API_ID"])
API_HASH       = os.environ["API_HASH"]
BOT_TOKEN      = os.environ["BOT_TOKEN"]
OWNER_ID       = int(os.environ["OWNER_ID"])
SESSION_STRING = os.environ["SESSION_STRING"]

# ── Two clients: user account (for VC) + bot (for commands) ──────────────────
user_client = Client("user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
bot_client  = Client("bot",  api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls   = PyTgCalls(user_client)

# ── Queue ─────────────────────────────────────────────────────────────────────
queues: dict[int, list[dict]] = {}

# ── Helpers ───────────────────────────────────────────────────────────────────
YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
    "outtmpl": "/tmp/%(id)s.%(ext)s",
}

def search_and_get_url(query: str):
    is_url = re.match(r"https?://", query)
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
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
    await pytgcalls.change_stream(chat_id, AudioPiped(track["path"], AudioParameters.from_quality("high")))

# ── Commands ──────────────────────────────────────────────────────────────────
@bot_client.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    is_owner = msg.from_user and msg.from_user.id == OWNER_ID
    owner_section = (
        "\n\n**👑 Owner Commands:**\n"
        "/broadcast `<message>` — Send to all groups & channels\n"
        "/listchats — List all chats where bot is admin"
    ) if is_owner else ""
    await msg.reply_text(
        "🎵 **Music Bot** — Play music in Voice Chats!\n\n"
        "**Commands:**\n"
        "/play `<song name or URL>` — Add to queue & play\n"
        "/skip — Skip current track\n"
        "/stop — Stop & leave VC\n"
        "/queue — Show queue\n"
        "/help — Show this message"
        + owner_section
    )

@bot_client.on_message(filters.command("help"))
async def cmd_help(_, msg: Message):
    await cmd_start(_, msg)

@bot_client.on_message(filters.command("play"))
async def cmd_play(_, msg: Message):
    chat_id = msg.chat.id
    query   = " ".join(msg.command[1:])
    if not query:
        await msg.reply_text("❌ Usage: `/play <song name or URL>`")
        return
    status_msg = await msg.reply_text("🔍 Searching...")
    try:
        title, path = await asyncio.get_event_loop().run_in_executor(None, search_and_get_url, query)
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: `{e}`")
        return
    track = {"title": title, "path": path}
    if chat_id not in queues:
        queues[chat_id] = []
    queues[chat_id].append(track)
    if len(queues[chat_id]) == 1:
        try:
            await pytgcalls.join_group_call(chat_id, AudioPiped(path, AudioParameters.from_quality("high")))
            await status_msg.edit_text(f"▶️ Now playing: **{title}**")
        except Exception as e:
            await status_msg.edit_text(f"❌ Could not join voice chat: `{e}`\nMake sure a Voice Chat is active.")
            queues[chat_id].pop()
    else:
        await status_msg.edit_text(f"✅ **{title}** added to queue (#{len(queues[chat_id])})")

@bot_client.on_message(filters.command("skip"))
async def cmd_skip(_, msg: Message):
    chat_id = msg.chat.id
    if not queues.get(chat_id):
        await msg.reply_text("❌ Queue is empty.")
        return
    queues[chat_id].pop(0)
    if queues[chat_id]:
        await play_next(chat_id)
        await msg.reply_text(f"⏭️ Now playing: **{queues[chat_id][0]['title']}**")
    else:
        await pytgcalls.leave_group_call(chat_id)
        await msg.reply_text("⏹️ Queue ended.")

@bot_client.on_message(filters.command("stop"))
async def cmd_stop(_, msg: Message):
    chat_id = msg.chat.id
    queues.pop(chat_id, None)
    try:
        await pytgcalls.leave_group_call(chat_id)
    except Exception:
        pass
    await msg.reply_text("⏹️ Stopped and left voice chat.")

@bot_client.on_message(filters.command("queue"))
async def cmd_queue(_, msg: Message):
    chat_id = msg.chat.id
    q = queues.get(chat_id, [])
    if not q:
        await msg.reply_text("📭 Queue is empty.")
        return
    lines = [f"{'▶️' if i == 0 else f'{i}.'} {t['title']}" for i, t in enumerate(q)]
    await msg.reply_text("🎶 **Queue:**\n" + "\n".join(lines))

@bot_client.on_message(filters.command("listchats") & filters.private)
async def cmd_listchats(_, msg: Message):
    if msg.from_user.id != OWNER_ID:
        await msg.reply_text("❌ Owner only.")
        return
    status_msg = await msg.reply_text("🔍 Scanning...")
    admin_chats = []
    async for dialog in bot_client.get_dialogs():
        chat = dialog.chat
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
            continue
        try:
            me = await bot_client.get_chat_member(chat.id, (await bot_client.get_me()).id)
            if me.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                kind = "📢" if chat.type == ChatType.CHANNEL else "👥"
                admin_chats.append(f"{kind} **{chat.title}** (`{chat.id}`)")
        except Exception:
            continue
    if not admin_chats:
        await status_msg.edit_text("😕 Not admin anywhere yet.")
        return
    await status_msg.edit_text(f"✅ **Admin in {len(admin_chats)} chats:**\n\n" + "\n".join(admin_chats))

@bot_client.on_message(filters.command("broadcast") & filters.private)
async def cmd_broadcast(_, msg: Message):
    if msg.from_user.id != OWNER_ID:
        await msg.reply_text("❌ Owner only.")
        return
    text  = " ".join(msg.command[1:])
    reply = msg.reply_to_message
    if not text and not reply:
        await msg.reply_text("❌ Usage: `/broadcast <message>` or reply to a message")
        return
    status_msg = await msg.reply_text("📡 Broadcasting...")
    sent = failed = 0
    me_id = (await bot_client.get_me()).id
    async for dialog in bot_client.get_dialogs():
        chat = dialog.chat
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
            continue
        try:
            member = await bot_client.get_chat_member(chat.id, me_id)
            if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                continue
            if reply:
                await reply.forward(chat.id)
            else:
                await bot_client.send_message(chat.id, text)
            sent += 1
            await asyncio.sleep(0.3)
        except Exception:
            failed += 1
    await status_msg.edit_text(f"📣 **Done!**\n✅ Sent: {sent}\n❌ Failed: {failed}")

@pytgcalls.on_stream_end()
async def on_stream_end(_, update):
    chat_id = update.chat_id
    if queues.get(chat_id):
        queues[chat_id].pop(0)
    await play_next(chat_id)

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    await user_client.start()
    await bot_client.start()
    await pytgcalls.start()
    print("✅ Bot is running...")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
