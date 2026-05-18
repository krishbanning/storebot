import asyncio
import aiohttp
import qrcode
import io
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply, CallbackQuery, Message
from config import ADMINS, PAYMENT_UPI_ID, BINANCE_ID, TRC20_ADDRESS, ADMIN_GROUP_ID
from database import get_user, update_balance, create_deposit, get_deposit
from utils import format_price
# In buttons ko yahan define kar dein taaki NameError na aaye
MAIN_BUTTONS = [
    "📱 Buy Accounts", "📂 Buy Sessions", 
    "👛 Add Funds", "👤 My Profile", 
    "💰 Earn Money", "📞 Support", "📖 How to Use"
]

# ==================================================================
# 🧠 DEPOSIT STATE MANAGEMENT
# ==================================================================
deposit_session = {}

def clear_deposit_session(user_id):
    if user_id in deposit_session:
        del deposit_session[user_id]

# ==================================================================
# 🏦 DEPOSIT MENU 
# ==================================================================
async def safe_deposit_menu(client, message_or_callback):
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇮🇳 Fampay", callback_data="pay_upi_start")],
        [InlineKeyboardButton("🪙 Crypto (Manual)", callback_data="pay_crypto")],
        [InlineKeyboardButton("🔙 Back to Home", callback_data="home")]
    ])
    user_id = message_or_callback.from_user.id
    clear_deposit_session(user_id)

    try:
        user = await get_user(user_id)
        balance_val = float(user.get("balance", 0)) if user else 0.0
        text = (
            f"<b>🏦 ADD FUNDS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Wallet Balance:</b> {format_price(balance_val)}\n\n"
            "👇 <b>Select Payment Method:</b>"
        )

        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text(text, reply_markup=buttons)
        else:
            await message_or_callback.reply_text(text, reply_markup=buttons)
    except Exception as e:
        await client.send_message(user_id, "<b>🏦 ADD FUNDS</b>\nSelect Method:", reply_markup=buttons)

@Client.on_message(filters.command("deposit"))
async def deposit_command(c, msg): await safe_deposit_menu(c, msg)

@Client.on_callback_query(filters.regex("deposit_home"))
async def deposit_callback(c, cb): await safe_deposit_menu(c, cb)

# =======================================
# ==================================================================
# 🇮🇳 FAMPAY AUTOMATIC FLOW (Step 1: Ask Amount)
# ==================================================================
@Client.on_callback_query(filters.regex("pay_upi_start"))
async def pay_upi_ask_amount(c, cb):
    user_id = cb.from_user.id
    deposit_session[user_id] = {"mode": "waiting_amount"}
    
    await cb.message.edit_text(
        "💰 <b>ENTER AMOUNT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Send the Amount You want deposit?\n"
        "<i>Example: 50, 100, 500</i>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="deposit_home")]])
    )

# ==================================================================
# 📸 STEP 2: Show QR & I Have Paid Button
# ==================================================================
@Client.on_message(filters.text & filters.private, group=3)
async def handle_deposit_amount(c, msg):
    user_id = msg.from_user.id
    if user_id not in deposit_session or deposit_session[user_id].get("mode") != "waiting_amount":
        return

    if not msg.text.isdigit():
        return await msg.reply_text("❌ Please enter a valid number (Amount).")

    amount = int(msg.text)
    deposit_session[user_id] = {"mode": "waiting_payment", "amount": amount}
    
    qr_url = "https://files.catbox.moe/ttkxgu.jpg" # Aapka QR
    text = (
        f"<b>💳 FAMPAY PAYMENT - ₹{amount}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ Pay on this Qr\n"
        "2️⃣ After Done the Payment then click on the button."
    )
    
    await c.send_photo(
        user_id, 
        photo=qr_url, 
        caption=text, 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ I HAVE PAID", callback_data="i_have_paid")]])
    )

# ==================================================================
# ⌨️ STEP 3: Ask UTR
# ==================================================================
@Client.on_callback_query(filters.regex("i_have_paid"))
async def ask_utr_after_pay(c, cb):
    user_id = cb.from_user.id
    if user_id not in deposit_session or "amount" not in deposit_session[user_id]:
        return await cb.answer("❌ Session expired. Start again.", show_alert=True)

    deposit_session[user_id]["mode"] = "waiting_utr"
    await cb.message.delete()
    await c.send_message(user_id, "🔢 <b>Now send your Transaction ID:</b>", reply_markup=ForceReply(selective=True))

# ==================================================================
# 🕵️‍♂️ STEP 4: Final Verification (Optimized)
# ==================================================================
@Client.on_message(filters.text & filters.private, group=1)
async def check_utr_input(c, msg):
    user_id = msg.from_user.id

    if user_id not in deposit_session or deposit_session[user_id].get("mode") != "waiting_utr":
        return

    if msg.text.startswith("/") or msg.text in MAIN_BUTTONS:
        if user_id in deposit_session:
            del deposit_session[user_id]
        return

    utr = msg.text.strip()

    if len(utr) < 8:
        return await msg.reply_text("❌ Please send a valid Transaction ID.")

    expected_amount = deposit_session[user_id]["amount"]
    status_msg = await c.send_message(user_id, "🔄 <b>Submitting payment...</b>")

    deposit_session[user_id]["mode"] = "waiting_screenshot"
    deposit_session[user_id]["utr"] = utr

    await status_msg.edit_text("📸 <b>Now send payment screenshot.</b>")

@Client.on_message(filters.photo & filters.private, group=4)
async def handle_fampay_screenshot(c, msg):
    user_id = msg.from_user.id

    if user_id not in deposit_session:
        return

    if deposit_session[user_id].get("mode") != "waiting_screenshot":
        return

    amount = deposit_session[user_id]["amount"]
    utr = deposit_session[user_id]["utr"]

    await c.send_photo(
        ADMIN_GROUP_ID,
        photo=msg.photo.file_id,
        caption=(
            f"💰 <b>Fampay Deposit Request</b>\n"
            f"User: `{user_id}`\n"
            f"Amount: ₹{amount}\n"
            f"UTR: `{utr}`"
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{user_id}_fampay")]
        ])
    )

    await msg.reply_text("✅ <b>Submitted!</b> Wait for admin approval.")

    clear_deposit_session(user_id)            
    


# ==================================================================
# 🪙 CRYPTO & ADMIN LOGIC
# ==================================================================
@Client.on_callback_query(filters.regex("pay_crypto"))
async def pay_crypto(c, cb):
    text = f"<b>🪙 CRYPTO DEPOSIT (USDT)</b>\n\n<b>🆔 Binance Pay ID:</b>\n<code>{BINANCE_ID}</code>\n\n<b>🔗 TRC20:</b>\n<code>{TRC20_ADDRESS}</code>"
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Upload Screenshot", callback_data="submit_crypto_proof")],[InlineKeyboardButton("🔙 Back", callback_data="deposit_home")]]))

@Client.on_callback_query(filters.regex("submit_crypto_proof"))
async def ask_proof(c, cb):
    deposit_session[cb.from_user.id] = {"mode": "waiting_proof"}
    await cb.message.delete()
    await c.send_message(cb.from_user.id, "<b>📸 Send Payment Screenshot Now.</b>", reply_markup=ForceReply(selective=True))

@Client.on_message(filters.photo & filters.private, group=2)
async def handle_crypto_proof(c, msg):
    user_id = msg.from_user.id
    if user_id not in deposit_session or deposit_session[user_id].get("mode") != "waiting_proof": return
    
    await c.send_photo(ADMIN_GROUP_ID, photo=msg.photo.file_id, caption=f"🪙 <b>Crypto Proof</b>\nUser: `{user_id}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{user_id}_crypto")]]))
    await msg.reply_text("✅ <b>Submitted!</b> Wait for admin check.")
    clear_deposit_session(user_id)

@Client.on_callback_query(filters.regex(r"admin_approve_(\d+)_(.+)"))
async def admin_approve_ask(c, cb):
    u_id = cb.data.split("_")[2]
    await cb.message.reply_text(f"💰 <b>Reply with Amount</b> for User: `{u_id}`", reply_markup=ForceReply(selective=True))

@Client.on_message(filters.reply & filters.regex(r"^\d+$") & filters.chat(ADMIN_GROUP_ID))
async def admin_finalize(c, msg):
    if "Reply with Amount" in msg.reply_to_message.text:
        try:
            target_id = int(msg.reply_to_message.text.split("User: `")[1].split("`")[0])
            amount = int(msg.text)
            await update_balance(target_id, amount)
            await msg.reply_text("✅ Done!")
            await c.send_message(target_id, f"✅ <b>Approved!</b> Added ₹{amount}")
        except Exception as e: await msg.reply_text(f"Error: {e}")

@Client.on_callback_query(filters.regex(r"manual_review_(\d+)"))
async def manual_req(c, cb):
    await c.send_message(ADMIN_GROUP_ID, f"⚠️ <b>Manual Review</b>\nUser: {cb.from_user.id}\nID: {cb.data.split('_')[2]}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{cb.from_user.id}_manual")]]))
    await cb.message.edit_text("✅ Sent!")
