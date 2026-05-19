import admin
import buy
import deposit
import redeem
import stock
import manager
import asyncio
import logging
import sys
from config import API_ID, API_HASH, BOT_TOKEN, ADMINS, LOG_CHANNEL, ADMIN_GROUP_ID
from hydrogram import Client, idle, enums

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = None


# ================= START BOT =================
async def start_bot():
    global app

    app = Client(
    "SimpleStoreUltimate",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML
    )
    
    await app.start()

    me = await app.get_me()

    admin_text = (
        "<b>⚡ SYSTEM REBOOTED</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 <b>Welcome Back, Master!</b>\n\n"
        f"🤖 <b>Identity:</b> @{me.username}\n"
        "⚙️ <b>Version:</b> <code>v7.5 (Ultimate)</code>\n"
        "🛡️ <b>Security:</b> <code>Active & Encrypted</code>\n"
        "📶 <b>Connection:</b> <code>Stable</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>🚀 All systems nominal. Waiting for commands...</i>"
    )

    log_text = (
        "<blockquote><b>🖥️ SERVER BOOT SEQUENCE</b></blockquote>\n"
        f"🤖 <b>Bot:</b> @{me.username}\n"
        f"🆔 <b>ID:</b> <code>{me.id}</code>\n"
        f"🐍 <b>Python:</b> <code>{sys.version.split()[0]} (Patched)</code>\n"
        "📂 <b>Modules:</b> <code>Loaded Successfully</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>STATUS:</b> 🟢 <b>OPERATIONAL</b>"
    )

    try:
        if ADMINS:
            await app.send_message(ADMINS[0], admin_text)

        if ADMIN_GROUP_ID:
            await app.send_message(ADMIN_GROUP_ID, log_text)

    except Exception as e:
        print(f"❌ Notification Error: {e}")

    await idle()
    await app.stop()


# ================= MAIN =================
if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("Bot stopped")
    except Exception as e:
        print(f"🔥 Fatal Error: {e}")
