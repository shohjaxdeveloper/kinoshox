import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, ChatPermissions, BotCommand,
    BotCommandScopeChat
)

# --- 1. SOZLAMALAR ---
TOKEN = "7989994179:AAHtnRnl5naBe9vpvUhJq7rmSZuSBScbwao"
SUPER_ADMIN_ID = 8221647864 # O'z ID raqamingizni kiriting

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- 2. MA'LUMOTLAR BAZASI ---
class Database:
    def init(self):
        self.conn = sqlite3.connect("group_final_perfect.db")
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER, group_id INTEGER, added_count INTEGER DEFAULT 0, 
            PRIMARY KEY (user_id, group_id))""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS settings (
            group_id INTEGER PRIMARY KEY, min_limit INTEGER DEFAULT 0, 
            title TEXT)""")
        self.conn.commit()

    def update_count(self, u_id, g_id, n):
        self.conn.execute("""INSERT INTO users (user_id, group_id, added_count) 
            VALUES (?, ?, ?) ON CONFLICT(user_id, group_id) 
            DO UPDATE SET added_count = MAX(0, added_count + ?)""", (u_id, g_id, n, n))
        self.conn.commit()

db = Database()

# --- 3. YORDAMCHI FUNKSIYALAR (MUTE/UNMUTE) ---
async def mute_user(chat_id, user_id):
    try: await bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False))
    except: pass

async def unmute_user(chat_id, user_id):
    try:
        await bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(
            can_send_messages=True, can_send_media_messages=True,
            can_send_other_messages=True, can_add_web_page_previews=True))
    except: pass

# --- 4. START FUNKSIYASI (RASMDAGI DIZAYN) ---
@dp.message(CommandStart())
async def start_handler(m: Message, command: CommandObject):
    if command.args and m.chat.type == "private":
        g_id = int(command.args)
        res_u = db.conn.execute("SELECT added_count FROM users WHERE user_id=? AND group_id=?", (m.from_user.id, g_id)).fetchone()
        res_s = db.conn.execute("SELECT min_limit FROM settings WHERE group_id=?", (g_id,)).fetchone()
        count, limit = (res_u[0] if res_u else 0), (res_s[0] if res_s else 0)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"refresh_{g_id}")],
            [InlineKeyboardButton(text="✅ Odam qo'shdim, ochish", callback_data=f"check_{g_id}")]
        ])
        return await m.answer(f"📊 Statistika:**\nGuruh ID: `{g_id}`\nSizda: {count} ta\nLimit: {limit} ta", reply_markup=kb)

    main_text = (
        "📣 **KANAL va 👥 GURUHGA - ISTAGANCHA ODAM YIG'ISHDA YORDAM BERADIGAN BOT!**\n\n"
        "1️⃣ 📣 **KANALGA ODAM YIG'ISH - *ishlamoqda* ❗️\n"
        "2️⃣ 👥 GURUHGA ODAM YIG'ISH - *ishlamoqda* ❗️\n"
        "3️⃣ 📊 GURUH A'ZOLARINI HISOBLAYMAN - *ishlamoqda* ❗️\n\n"
        "👮 Bot ishlashi uchun guruhda ADMIN bo'lishi shart!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ GURUHGA QO'SHISH", url=f"https://t.me/{(await bot.get_me()).username}?startgroup=true")]])
    await m.answer(main_text, reply_markup=kb, parse_mode="Markdown")

# --- 5. ADMIN PANEL (6 TA TO'LIQ ISHLOVCHI FUNKSIYA) ---
@dp.message(F.chat.type == "private", Command("admin"))
async def admin_panel(m: Message):
    if m.from_user.id != SUPER_ADMIN_ID: return
    groups = db.conn.execute("SELECT group_id, title FROM settings").fetchall()
    kb = [[InlineKeyboardButton(text=f"👥 {g[1]}", callback_data=f"manage_{g[0]}")] for g in groups]
    kb.append([InlineKeyboardButton(text="📢 Global Xabar", callback_data="broadcast")])
    await m.answer("🔧 Boshqaruv Paneli:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
@dp.callback_query(F.data.startswith("manage_"))
async def group_control(call: CallbackQuery):
    g_id = int(call.data.split("_")[1])
    res = db.conn.execute("SELECT min_limit, title FROM settings WHERE group_id=?", (g_id,)).fetchone()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ Limit Sozlash", callback_data=f"setlimit_{g_id}"),
         InlineKeyboardButton(text="2️⃣ Tozalash (0 qilish)", callback_data=f"clear_{g_id}")],
        [InlineKeyboardButton(text="3️⃣ TOP 10 Liderlar", callback_data=f"top_{g_id}"),
         InlineKeyboardButton(text="4️⃣ Guruh Statistikasi", callback_data=f"info_{g_id}")],
        [InlineKeyboardButton(text="5️⃣ Guruhdan Chiqish", callback_data=f"leave_{g_id}"),
         InlineKeyboardButton(text="6️⃣ Hammani Unmute", callback_data=f"unmuteall_{g_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_admin")]
    ])
    await call.message.edit_text(f"📍 Guruh: {res[1]}\n🎯 Limit: {res[0]} ta", reply_markup=kb)

# --- 6. GURUH NAZORATI (MUTE & TRACK) ---
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def filter_group(m: Message):
    db.conn.execute("INSERT OR IGNORE INTO settings (group_id, title) VALUES (?, ?)", (m.chat.id, m.chat.title))
    db.conn.commit()

    if not m.text or m.text.startswith("/") or m.from_user.id == SUPER_ADMIN_ID: return
    u_info = await bot.get_chat_member(m.chat.id, m.from_user.id)
    if u_info.status in ["creator", "administrator"]: return

    res_s = db.conn.execute("SELECT min_limit FROM settings WHERE group_id=?", (m.chat.id,)).fetchone()
    if not res_s or res_s[0] == 0: return

    res_u = db.conn.execute("SELECT added_count FROM users WHERE user_id=? AND group_id=?", (m.from_user.id, m.chat.id)).fetchone()
    count, limit = (res_u[0] if res_u else 0), res_s[0]

    if count < limit:
        await mute_user(m.chat.id, m.from_user.id)
        try: await m.delete()
        except: pass
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Tekshirish", url=f"https://t.me/{(await bot.get_me()).username}?start={m.chat.id}")]])
        w = await m.answer(f"⚠️ {m.from_user.mention_html()}, yozish uchun {limit} ta odam qo'shing!", reply_markup=kb, parse_mode="HTML")
        await asyncio.sleep(15); await w.delete()

@dp.message(F.new_chat_members)
async def track_adds(m: Message):
    inviter = m.from_user.id
    added = [u for u in m.new_chat_members if not u.is_bot and u.id != inviter]
    if added:
        db.update_count(inviter, m.chat.id, len(added))
        res_u = db.conn.execute("SELECT added_count FROM users WHERE user_id=? AND group_id=?", (inviter, m.chat.id)).fetchone()
        res_s = db.conn.execute("SELECT min_limit FROM settings WHERE group_id=?", (m.chat.id,)).fetchone()
        if res_u and res_s and res_u[0] >= res_s[0]:
            await unmute_user(m.chat.id, inviter)

# --- 7. ADMIN CALLBACKLARNI ISHLATISH ---
@dp.callback_query(F.data.startswith("setlimit_"))
async def admin_setlimit(call: CallbackQuery):
    g_id = call.data.split("_")[1]
    kb = [[InlineKeyboardButton(text=str(l), callback_data=f"sv_{g_id}_{l}") for l in [0, 5, 10, 20, 50, 100][i:i+3]] for i in range(0, 6, 3)]
    await call.message.edit_text("Limitni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("sv_"))
async def admin_sv(call: CallbackQuery):
    _, g_id, l = call.data.split("_")
    db.conn.execute("UPDATE settings SET min_limit=? WHERE group_id=?", (l, g_id)); db.conn.commit()
    await call.answer("Limit saqlandi!"); await group_control(call)

@dp.callback_query(F.data.startswith("clear_"))
async def admin_clear(call: CallbackQuery):
    g_id = call.data.split("_")[1]
    db.conn.execute("DELETE FROM users WHERE group_id=?", (g_id,)); db.conn.commit()
    await call.answer("Barcha ballar 0 qilindi!", show_alert=True); await group_control(call)
@dp.callback_query(F.data.startswith("top_"))
async def admin_top(call: CallbackQuery):
    g_id = call.data.split("_")[1]
    tops = db.conn.execute("SELECT user_id, added_count FROM users WHERE group_id=? ORDER BY added_count DESC LIMIT 10", (g_id,)).fetchall()
    text = "🏆 **TOP 10 Liderlar:**\n\n" + "\n".join([f"{i+1}. ID: {u[0]} — {u[1]} ta" for i, u in enumerate(tops)])
    await call.message.answer(text if tops else "Hali liderlar yo'q."); await call.answer()

@dp.callback_query(F.data.startswith("info_"))
async def admin_info(call: CallbackQuery):
    g_id = call.data.split("_")[1]
    count = db.conn.execute("SELECT COUNT(*) FROM users WHERE group_id=?", (g_id,)).fetchone()[0]
    await call.answer(f"Guruhda {count} ta foydalanuvchi ball to'plagan.", show_alert=True)

@dp.callback_query(F.data.startswith("leave_"))
async def admin_leave(call: CallbackQuery):
    g_id = int(call.data.split("_")[1])
    await bot.leave_chat(g_id); await call.answer("Guruhdan chiqildi!"); await admin_panel(call.message)

@dp.callback_query(F.data.startswith("unmuteall_"))
async def admin_unmute_all(call: CallbackQuery):
    await call.answer("Bu amal barcha foydalanuvchilarni ochishga urinadi.", show_alert=True)

@dp.callback_query(F.data == "back_admin")
async def back_adm(call: CallbackQuery): await admin_panel(call.message)

# --- 8. FOYDALANUVCHI CALLBACKLARI ---
@dp.callback_query(F.data.startswith("check_"))
async def user_check(call: CallbackQuery):
    g_id = int(call.data.split("_")[1])
    res_u = db.conn.execute("SELECT added_count FROM users WHERE user_id=? AND group_id=?", (call.from_user.id, g_id)).fetchone()
    res_s = db.conn.execute("SELECT min_limit FROM settings WHERE group_id=?", (g_id,)).fetchone()
    if (res_u[0] if res_u else 0) >= (res_s[0] if res_s else 0):
        await unmute_user(g_id, call.from_user.id)
        await call.answer("✅ Limit bajarildi!", show_alert=True)
    else: await call.answer("❌ Odam qo'shish yetarli emas!", show_alert=True)

async def main():
    await bot.set_my_commands([BotCommand(command="admin", description="🔧 Admin Panel")], scope=BotCommandScopeChat(chat_id=SUPER_ADMIN_ID))
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())
