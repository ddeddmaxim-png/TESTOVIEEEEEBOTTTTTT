import asyncio
import logging
import os
import csv
import io
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery, ReplyKeyboardRemove
from aiocryptopay import AioCryptoPay, Networks

# --- АВТОМАТИЧЕСКИЙ ПЕРЕНОС БД В БЕЗОПАСНУЮ ПАПКУ НА ХОСТИНГЕ ---
_original_connect = aiosqlite.connect
def secure_connect(database, *args, **kwargs):
    if database == "tariffs.db":
        # На хостинге сохраняем в /app/data, на ПК при тестах — в текущую папку
        db_dir = '/app/data'
        if os.path.exists(db_dir) or os.getenv('DATA_DIR'):
            os.makedirs(db_dir, exist_ok=True)
            database = os.path.join(db_dir, "tariffs.db")
    return _original_connect(database, *args, **kwargs)
aiosqlite.connect = secure_connect
# ---------------------------------------------------------------

# --- КОНФИГ ---
CUSTOM_BOT_TOKEN = "" 
BOT_TOKEN = CUSTOM_BOT_TOKEN or os.getenv("BOT_TOKEN")
PAYMENT_BOT_TOKEN = "" # Токен бота Б для звезд
ADMIN_ID =   # ВСТАВЬ СВОЙ ID СЮДА

# --- ТОКЕН CRYPTO PAY ---
CRYPTO_PAY_TOKEN = "" # ВСТАВЬ ТОКЕН СЮДА

bot_main = Bot(token=BOT_TOKEN)
bot_pay = Bot(token=PAYMENT_BOT_TOKEN) # Бот для приема платежей Stars
dp = Dispatcher(storage=MemoryStorage())

# Инициализация клиента CryptoBot
crypto = AioCryptoPay(token=CRYPTO_PAY_TOKEN, network=Networks.MAIN_NET)

logging.basicConfig(level=logging.INFO)

# --- ТЕКСТЫ ИНТЕРФЕЙСА (ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ТОЛЬКО EN) ---
TEXTS = {
    "en": {
        "no_cats": "😔 No categories available.",
        "select_cat": "📁 Select category:",
        "no_tariffs": "No tariffs here yet.",
        "select_tariff": "📊 Category <b>{name}</b>. Select tariff:",
        "back_to_cats": "⬅️ Back to categories",
        "back_to_tariffs": "⬅️ Back to tariffs",
        "stars_btn": "🌟 Telegram Stars ({stars} XTR)",
        "crypto_btn": "⚡ CryptoBot (${price})",
        "stars_invoice_title": "Tariff {name}",
        "stars_invoice_desc": "Access to {name}",
        "invoice_error": "❌ Invoice error.",
        "success_pay_stars": "🎉 Payment successful! Tariff activated.",
        "promo_btn": "🎟 Use Promo Code",
        "promo_success": "✅ Applied! {pct}% discount.\nNew Stars price: <b>{s_price} XTR</b>\nNew Crypto price: <b>${c_price:.2f}</b>",
        "promo_not_found": "❌ Promo code not found.",
        "custom_pay_prompt": "📸 Send a <b>screenshot of the receipt</b> here:",
        "custom_pay_sent": "⏳ Receipt sent for verification!",
        "custom_pay_approved": "🎉 Administrator approved! Activated.",
        "custom_pay_rejected": "❌ Payment rejected."
    }
}

# --- ИНИЦИАЛИЗАЦИЯ БД ---
async def init_db():
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0)")
        await db.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS tariffs (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, price_stars INTEGER, price_crypto REAL, description TEXT DEFAULT 'No description')")
        try: await db.execute("ALTER TABLE tariffs ADD COLUMN description TEXT DEFAULT 'No description'")
        except Exception: pass
        await db.execute("CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, val TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS custom_payment_methods (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, instruction TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, discount REAL)")
        await db.execute("CREATE TABLE IF NOT EXISTS purchase_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, price_stars INTEGER, price_crypto REAL, date TEXT DEFAULT CURRENT_TIMESTAMP)")
        
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES ('welcome', '👋 Welcome to our store!')")
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES ('support', '📝 Support: @admin')")
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES ('reviews', '💬 Reviews channel: @reviews')")
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES ('payment_title', '💳 Payment for: <b>{name}</b>\\nChoose method:')")
        
        # Дефолтные названия кнопок главного экрана
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES ('btn_buy', '💎 Buy Tariff')")
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES ('btn_profile', '👤 Profile')")
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES ('btn_support', '👨‍💻 Support')")
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES ('btn_reviews', '⭐ Reviews')")
        
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES ('auto_remind_text', 'Hey! Still thinking? Use promo code <b>{code}</b> to get a {percent}% discount on any tariff!')")
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES ('auto_remind_percent', '15')")
        await db.commit()

# --- ТАЙМЕРЫ АВТО-УВЕДОМЛЕНИЙ ---
active_timers = {}

async def reminder_task(user_id):
    await asyncio.sleep(600)  # 10 минут
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT val FROM system_settings WHERE key='auto_remind_percent'") as cur:
            row = await cur.fetchone()
            percent = float(row[0]) if row else 15.0
        async with db.execute("SELECT val FROM system_settings WHERE key='auto_remind_text'") as cur:
            row = await cur.fetchone()
            text = row[0] if row else "Use promo code {code} to get a {percent}% discount!"
        
        code = f"SALE{user_id}"
        await db.execute("INSERT OR REPLACE INTO promo_codes (code, discount) VALUES (?, ?)", (code, percent))
        await db.commit()
        
    msg = text.replace("{percent}", str(percent)).replace("{code}", code)
    try: await bot_main.send_message(user_id, msg, parse_mode="HTML")
    except Exception: pass
    
    if user_id in active_timers: del active_timers[user_id]

def start_reminder_timer(user_id):
    if user_id == ADMIN_ID: return
    if user_id in active_timers: active_timers[user_id].cancel()
    active_timers[user_id] = asyncio.create_task(reminder_task(user_id))

def cancel_reminder_timer(user_id):
    if user_id in active_timers:
        active_timers[user_id].cancel()
        del active_timers[user_id]

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def get_custom_text(key: str):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT val FROM system_settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "Text not found"

async def update_custom_text(key: str, new_text: str):
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("UPDATE system_settings SET val = ? WHERE key = ?", (new_text, key))
        await db.commit()

def parse_multilang_text(text: str, is_admin: bool):
    if not text: return "Unnamed"
    if " / " in text:
        parts = text.split(" / ")
        return parts[0].strip() if is_admin else parts[1].strip()
    return text

def get_user_mention(user: types.User) -> str:
    if user.username: return f"@{user.username} (ID: {user.id})"
    return f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"

async def notify_admin(action_text: str):
    try: await bot_main.send_message(ADMIN_ID, f"👁 <b>Лог:</b>\n{action_text}", parse_mode="HTML")
    except Exception: pass

def get_discounted_price(price: float, discount_pct: float) -> float:
    return max(0.0, float(price) * (1 - discount_pct / 100.0))

def get_discounted_stars(stars: int, discount_pct: float) -> int:
    return max(1, int(float(stars) * (1 - discount_pct / 100.0)))


# --- MIDDLEWARES ---
@dp.callback_query.middleware
async def log_cb_middleware(handler, event: types.CallbackQuery, data):
    if event.from_user.id != ADMIN_ID:
        btn_text = "Неизвестная кнопка"
        if event.message and event.message.reply_markup:
            for row in event.message.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data == event.data:
                        btn_text = btn.text
                        break
        await notify_admin(f"👤 {get_user_mention(event.from_user)}\n🔘 Нажал: <b>{btn_text}</b>")
    return await handler(event, data)


# --- FSM СОСТОЯНИЯ ---
class AdminStates(StatesGroup):
    cat_name, t_name, t_desc, t_stars, t_crypto, edit_text, pm_title, pm_instruction, broadcast_msg, promo_code, promo_discount, edit_price, auto_remind_text, auto_remind_pct = State(), State(), State(), State(), State(), State(), State(), State(), State(), State(), State(), State(), State(), State()

class UserStates(StatesGroup):
    promo_apply = State()   
    custom_receipt = State()


# --- ИНЛАЙН КЛАВИАТУРЫ ---
async def get_main_menu_inline(user_id: int):
    btn_buy_text = await get_custom_text("btn_buy")
    btn_profile_text = await get_custom_text("btn_profile")
    btn_support_text = await get_custom_text("btn_support")
    btn_reviews_text = await get_custom_text("btn_reviews")
    
    kb = [
        [InlineKeyboardButton(text=btn_buy_text, callback_data="main_buy")],
        [InlineKeyboardButton(text=btn_profile_text, callback_data="main_profile")],
        [
            InlineKeyboardButton(text=btn_support_text, callback_data="main_support"), 
            InlineKeyboardButton(text=btn_reviews_text, callback_data="main_reviews")
        ]
    ]
    if user_id == ADMIN_ID: 
        kb.append([InlineKeyboardButton(text="⚙️ Админ Панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_admin_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 + Категория", callback_data="adm_add_cat"), InlineKeyboardButton(text="🗑 Удалить Категорию", callback_data="adm_del_cat_start")],
        [InlineKeyboardButton(text="➕ + Тариф", callback_data="adm_add_tariff"), InlineKeyboardButton(text="🗑 Удалить Тариф", callback_data="adm_del_tariff_start")],
        [InlineKeyboardButton(text="✏️ Изменить Цену", callback_data="adm_edit_tariff_start"), InlineKeyboardButton(text="🎟 Промокоды", callback_data="adm_promos")],
        [InlineKeyboardButton(text="📝 Тексты и Кнопки", callback_data="adm_manage_texts"), InlineKeyboardButton(text="🕒 Авто-скидка (10 мин)", callback_data="adm_auto_remind")],
        [InlineKeyboardButton(text="💳 Свои Оплаты", callback_data="adm_manage_payments"), InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats"), InlineKeyboardButton(text="📥 Выгрузить продажи (CSV)", callback_data="adm_export")],
        [InlineKeyboardButton(text="❌ Выход в меню юзера", callback_data="back_to_main_user")]
    ])

def get_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel and return", callback_data="cancel_action")]
    ])

# ==========================================
# 🛑 ОТМЕНА ДЕЙСТВИЙ И ВОЗВРАТ
# ==========================================
@dp.callback_query(F.data == "cancel_action")
async def cancel_action_cb(c: types.CallbackQuery, state: FSMContext):
    await state.clear() 
    try: await c.message.delete() 
    except: pass
    
    is_admin = (c.from_user.id == ADMIN_ID)
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cursor: cats = await cursor.fetchall()
    
    if not cats: 
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main_user")]])
        return await c.message.answer("❌ Action cancelled.\n\n" + TEXTS["en"]["no_cats"], reply_markup=kb)
        
    kb = [[InlineKeyboardButton(text=parse_multilang_text(cat[1], is_admin), callback_data=f"cat_{cat[0]}")] for cat in cats]
    kb.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main_user")])
    await c.message.answer("❌ Cancelled.\n\n" + TEXTS["en"]["select_cat"], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = await get_custom_text("welcome")
    await message.answer("❌ Action cancelled.", reply_markup=await get_main_menu_inline(message.from_user.id))

# ==========================================
# 👤 ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ
# ==========================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()
    
    if user_id != ADMIN_ID:
        await notify_admin(f"👤 {get_user_mention(message.from_user)}\n▶️ Нажал /start")
        start_reminder_timer(user_id)
        
    temp = await message.answer("🔄 Loading interface...", reply_markup=ReplyKeyboardRemove())
    await temp.delete()
        
    welcome_text = await get_custom_text("welcome")
    await message.answer(welcome_text, reply_markup=await get_main_menu_inline(user_id))

@dp.message(F.text.in_({"💎 Buy Tariff", "👤 Profile", "👨‍💻 Support", "⭐ Reviews", "⚙️ Админ Панель"}))
async def clean_old_buttons(message: types.Message):
    temp = await message.answer("🔄 Updating menu...", reply_markup=ReplyKeyboardRemove())
    await temp.delete()
    welcome_text = await get_custom_text("welcome")
    await message.answer(welcome_text, reply_markup=await get_main_menu_inline(message.from_user.id))

@dp.callback_query(F.data == "back_to_main_user")
async def back_to_main_user_cb(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    welcome_text = await get_custom_text("welcome")
    await c.message.edit_text(welcome_text, reply_markup=await get_main_menu_inline(c.from_user.id))

@dp.callback_query(F.data == "main_profile")
async def show_profile_inline(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT item_name, price_crypto, date FROM purchase_history WHERE user_id = ? ORDER BY id DESC LIMIT 5", (c.from_user.id,)) as cursor:
            history = await cursor.fetchall()
    h_text = "".join([f"▪️ {i[0]} (${i[1]}) — {i[2]}\n" for i in history]) or "Empty"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main_user")]
    ])
    await c.message.edit_text(f"👤 <b>Profile</b>\n\n🆔 ID: <code>{c.from_user.id}</code>\n\n<b>Purchases:</b>\n{h_text}", parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "main_support")
async def show_support_inline(c: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main_user")]
    ])
    await c.message.edit_text(await get_custom_text("support"), parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "main_reviews")
async def show_reviews_inline(c: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main_user")]
    ])
    await c.message.edit_text(await get_custom_text("reviews"), parse_mode="HTML", reply_markup=kb)

# --- ВИТРИНА КАТЕГОРИЙ ---
@dp.callback_query(F.data == "main_buy")
async def buy_tariff_inline(c: types.CallbackQuery):
    is_admin = (c.from_user.id == ADMIN_ID)
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cursor: cats = await cursor.fetchall()
    
    if not cats: 
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main_user")]
        ])
        return await c.message.edit_text(TEXTS["en"]["no_cats"], reply_markup=kb)
        
    kb = [[InlineKeyboardButton(text=parse_multilang_text(cat[1], is_admin), callback_data=f"cat_{cat[0]}")] for cat in cats]
    kb.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main_user")])
    await c.message.edit_text(TEXTS["en"]["select_cat"], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "back_to_cats")
async def back_to_cats_cb(c: types.CallbackQuery):
    is_admin = (c.from_user.id == ADMIN_ID)
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cursor: cats = await cursor.fetchall()
    kb = [[InlineKeyboardButton(text=parse_multilang_text(cat[1], is_admin), callback_data=f"cat_{cat[0]}")] for cat in cats]
    kb.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_main_user")])
    await c.message.edit_text(TEXTS["en"]["select_cat"], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("cat_"))
async def select_category(c: types.CallbackQuery):
    is_admin = (c.from_user.id == ADMIN_ID)
    cat_id = int(c.data.split("_")[1])
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)) as cursor: 
            row = await cursor.fetchone()
            cat_name = row[0] if row else "Unknown"
        async with db.execute("SELECT * FROM tariffs WHERE category_id = ?", (cat_id,)) as cursor: tariffs = await cursor.fetchall()

    if not tariffs: return await c.answer(TEXTS["en"]["no_tariffs"], show_alert=True)
    kb = [[InlineKeyboardButton(text=f"{parse_multilang_text(t[2], is_admin)} (${t[4]})", callback_data=f"select_{t[0]}")] for t in tariffs]
    kb.append([InlineKeyboardButton(text=TEXTS["en"]["back_to_cats"], callback_data="back_to_cats")])
    await c.message.edit_text(TEXTS["en"]["select_tariff"].format(name=parse_multilang_text(cat_name, is_admin)), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("select_"))
async def select_method(c: types.CallbackQuery, state: FSMContext):
    await state.clear() 
    is_admin = (c.from_user.id == ADMIN_ID)
    t_id = int(c.data.split("_")[1])
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM tariffs WHERE id = ?", (t_id,)) as cursor: t = await cursor.fetchone()
        async with db.execute("SELECT id, title FROM custom_payment_methods") as cursor: custom_methods = await cursor.fetchall()

    if not t: return
    t_name, t_desc = parse_multilang_text(t[2], is_admin), parse_multilang_text(t[5], is_admin)
    
    kb = [
        [InlineKeyboardButton(text=TEXTS["en"]["stars_btn"].format(stars=t[3]), callback_data=f"stars_{t[0]}")],
        [InlineKeyboardButton(text=TEXTS["en"]["crypto_btn"].format(price=t[4]), callback_data=f"crypto_{t[0]}")],
        [InlineKeyboardButton(text=TEXTS["en"]["promo_btn"], callback_data=f"applypromo_{t[0]}")] 
    ]
    for cm in custom_methods: kb.append([InlineKeyboardButton(text=parse_multilang_text(cm[1], is_admin), callback_data=f"custpay_{cm[0]}_{t[0]}")])
    kb.append([InlineKeyboardButton(text=TEXTS["en"]["back_to_tariffs"], callback_data=f"cat_{t[1]}")])
    
    pay_text = (await get_custom_text("payment_title")).format(name=t_name)
    await c.message.edit_text(f"📦 <b>{t_name}</b>\n\n📝 <i>{t_desc}</i>\n\n{pay_text}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# --- ПРОМОКОДЫ ---
@dp.callback_query(F.data.startswith("applypromo_"))
async def user_promo_start(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(t_id=int(c.data.split("_")[1]))
    await state.set_state(UserStates.promo_apply)
    await c.message.edit_text("🎟 Send promo code:", reply_markup=get_cancel_kb())

@dp.message(UserStates.promo_apply)
async def user_promo_finish(m: types.Message, state: FSMContext):
    is_admin = (m.from_user.id == ADMIN_ID)
    code = m.text.strip().upper()
    t_id = (await state.get_data())['t_id']
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT discount FROM promo_codes WHERE code = ?", (code,)) as cur: promo = await cur.fetchone()
        async with db.execute("SELECT * FROM tariffs WHERE id = ?", (t_id,)) as cur: t = await cur.fetchone()
        async with db.execute("SELECT id, title FROM custom_payment_methods") as cur: custom_methods = await cur.fetchall()
    
    if not promo or not t: 
        return await m.answer(TEXTS["en"]["promo_not_found"], reply_markup=get_cancel_kb())
    
    discount_pct = float(promo[0])
    new_crypto = get_discounted_price(t[4], discount_pct)
    new_stars = get_discounted_stars(t[3], discount_pct)
    
    await state.clear()
    await m.answer(TEXTS["en"]["promo_success"].format(pct=discount_pct, s_price=new_stars, c_price=new_crypto), parse_mode="HTML")
    
    kb = [
        [InlineKeyboardButton(text=TEXTS["en"]["stars_btn"].format(stars=new_stars), callback_data=f"stars_{t[0]}?promo={code}")],
        [InlineKeyboardButton(text=TEXTS["en"]["crypto_btn"].format(price=new_crypto), callback_data=f"crypto_{t[0]}?promo={code}")]
    ]
    for cm in custom_methods: kb.append([InlineKeyboardButton(text=parse_multilang_text(cm[1], is_admin), callback_data=f"custpay_{cm[0]}_{t[0]}?promo={code}")])
    kb.append([InlineKeyboardButton(text=TEXTS["en"]["back_to_tariffs"], callback_data=f"cat_{t[1]}")])
    
    pay_text = (await get_custom_text("payment_title")).format(name=parse_multilang_text(t[2], is_admin))
    await m.answer(f"📦 <b>{parse_multilang_text(t[2], is_admin)}</b>\n\n{pay_text}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# --- ОПЛАТА STARS ---
@dp.callback_query(F.data.startswith("stars_"))
async def pay_stars(c: types.CallbackQuery):
    is_admin = (c.from_user.id == ADMIN_ID)
    t_id = int(c.data.split("_")[1].split("?")[0])
    
    discount_pct = 0.0
    if "?promo=" in c.data:
        code = c.data.split("?promo=")[1]
        async with aiosqlite.connect("tariffs.db") as db:
            async with db.execute("SELECT discount FROM promo_codes WHERE code = ?", (code,)) as cur:
                p = await cur.fetchone()
                if p: discount_pct = float(p[0])

    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM tariffs WHERE id = ?", (t_id,)) as cursor: t = await cursor.fetchone()
    
    final_stars = get_discounted_stars(t[3], discount_pct)
    
    try:
        invoice_link = await bot_pay.create_invoice_link(
            title=TEXTS["en"]["stars_invoice_title"].format(name=parse_multilang_text(t[2], is_admin)),
            description=TEXTS["en"]["stars_invoice_desc"].format(name=parse_multilang_text(t[2], is_admin)),
            payload=f"stars_{t[0]}_{final_stars}",
            currency="XTR",
            prices=[LabeledPrice(label="Tariff", amount=final_stars)]
        )
        
        pay_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Pay (Telegram Stars)", url=invoice_link)],
            [InlineKeyboardButton(text="❌ Cancel and return", callback_data="cancel_action")]
        ])
        await c.message.edit_text(f"Payment link generated:", reply_markup=pay_kb)
    except Exception as e: 
        logging.error(f"Invoice err: {e}")
        await c.message.answer(TEXTS["en"]["invoice_error"], reply_markup=get_cancel_kb())

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery): 
    await q.answer(ok=True)

@dp.message(F.successful_payment)
async def success_pay(m: types.Message):
    cancel_reminder_timer(m.from_user.id)
    
    t_id = m.successful_payment.invoice_payload.split("_")[1]
    amount = m.successful_payment.total_amount
    
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT INTO purchase_history (user_id, item_name, price_stars, price_crypto) VALUES (?, ?, ?, 0)", (m.from_user.id, f"Tariff {t_id} (Stars)", amount))
        await db.commit()
        
    await notify_admin(f"💰 <b>ОПЛАТА STARS!</b>\nЮзер: {get_user_mention(m.from_user)}\nСумма: {amount} XTR\nТариф: {t_id}")
    try: await bot_main.send_message(m.from_user.id, TEXTS["en"]["success_pay_stars"])
    except Exception: pass

# --- ОПЛАТА CRYPTOBOT (АВТОМАТИЧЕСКАЯ) ---
@dp.callback_query(F.data.startswith("crypto_"))
async def pay_crypto(c: types.CallbackQuery, state: FSMContext):
    t_id = int(c.data.split("_")[1].split("?")[0])
    
    discount_pct = 0.0
    if "?promo=" in c.data:
        code = c.data.split("?promo=")[1]
        async with aiosqlite.connect("tariffs.db") as db:
            async with db.execute("SELECT discount FROM promo_codes WHERE code = ?", (code,)) as cur:
                p = await cur.fetchone()
                if p: discount_pct = float(p[0])

    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT price_crypto FROM tariffs WHERE id = ?", (t_id,)) as cur: 
            t = await cur.fetchone()
    
    final_price = get_discounted_price(t[0], discount_pct)
    
    try:
        # Создаем счет через API
        invoice = await crypto.create_invoice(
            amount=final_price,
            fiat='USD',
            currency_type='fiat',
            description=f"Payment for Tariff {t_id}"
        )
        
        pay_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Pay in CryptoBot", url=invoice.bot_invoice_url)],
            [InlineKeyboardButton(text="🔄 Check Payment", callback_data=f"chk_crypt_{invoice.invoice_id}_{t_id}_{final_price}")],
            [InlineKeyboardButton(text="❌ Cancel and return", callback_data="cancel_action")]
        ])
        
        msg_text = (
            f"⚡ <b>Payment via CryptoBot</b>\n\n"
            f"Amount: <b>${final_price:.2f}</b>\n\n"
            f"Click the button below to pay, then return and click «Check Payment»."
        )
        await c.message.edit_text(msg_text, parse_mode="HTML", reply_markup=pay_kb)
        
    except Exception as e:
        logging.error(f"CryptoBot Invoice error: {e}")
        await c.message.answer("❌ Error creating invoice. Please try again later.", reply_markup=get_cancel_kb())

# --- ПРОВЕРКА ИНВОЙСА CRYPTOBOT ---
@dp.callback_query(F.data.startswith("chk_crypt_"))
async def check_crypto_payment(c: types.CallbackQuery):
    data_parts = c.data.split("_")
    invoice_id = int(data_parts[2])
    t_id = int(data_parts[3])
    price = float(data_parts[4])
    
    try:
        invoices = await crypto.get_invoices(invoice_ids=invoice_id)
        if not invoices:
            return await c.answer("❌ Invoice not found.", show_alert=True)
            
        invoice = invoices[0]
        
        if invoice.status == 'paid':
            cancel_reminder_timer(c.from_user.id)
            
            async with aiosqlite.connect("tariffs.db") as db:
                await db.execute(
                    "INSERT INTO purchase_history (user_id, item_name, price_stars, price_crypto) VALUES (?, ?, 0, ?)", 
                    (c.from_user.id, f"Tariff {t_id} (CryptoBot)", price)
                )
                await db.commit()
                
            await notify_admin(
                f"💰 <b>ОПЛАТА CRYPTOBOT (АВТОМАТ)</b>\n"
                f"Юзер: {get_user_mention(c.from_user)}\n"
                f"Сумма: ${price:.2f}\n"
                f"Тариф ID: {t_id}"
            )
            
            try: await bot_main.send_message(c.from_user.id, "🎉 Payment successful! Tariff activated.")
            except Exception: pass
                
            await c.message.edit_text("✅ Payment successfully verified and tariff activated!", reply_markup=None)
            
        elif invoice.status == 'expired':
            await c.answer("❌ Time is up. This invoice is expired. Please create a new one.", show_alert=True)
        else:
            await c.answer("⏳ Payment not received yet. Check again after you pay.", show_alert=True)
            
    except Exception as e:
        logging.error(f"Invoice check error: {e}")
        await c.answer("❌ Error checking invoice.", show_alert=True)


# --- СВОИ МЕТОДЫ ОПЛАТЫ ---
@dp.callback_query(F.data.startswith("custpay_"))
async def custom_pay_start(c: types.CallbackQuery, state: FSMContext):
    is_admin = (c.from_user.id == ADMIN_ID)
    pm_id = int(c.data.split("_")[1])
    t_id = int(c.data.split("_")[2].split("?")[0])
    
    discount_pct = 0.0
    if "?promo=" in c.data:
        code = c.data.split("?promo=")[1]
        async with aiosqlite.connect("tariffs.db") as db:
            async with db.execute("SELECT discount FROM promo_codes WHERE code = ?", (code,)) as cur:
                p = await cur.fetchone()
                if p: discount_pct = float(p[0])

    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT instruction FROM custom_payment_methods WHERE id = ?", (pm_id,)) as cur: pm = await cur.fetchone()
        async with db.execute("SELECT price_crypto FROM tariffs WHERE id = ?", (t_id,)) as cur: t = await cur.fetchone()
        
    final_price = get_discounted_price(t[0], discount_pct)
        
    await state.update_data(t_id=t_id, pm_id=pm_id, price=final_price)
    await state.set_state(UserStates.custom_receipt)
    instr = parse_multilang_text(pm[0], is_admin)
    
    msg_text = f"{instr}\n\n"
    if discount_pct > 0: msg_text += f"📉 Discount applied: <b>{discount_pct}%</b>\nTotal to pay: <b>${final_price:.2f}</b>\n\n"
    msg_text += TEXTS["en"]['custom_pay_prompt']
    
    await c.message.edit_text(msg_text, parse_mode="HTML", reply_markup=get_cancel_kb())

@dp.message(UserStates.custom_receipt, F.photo)
async def custom_pay_receipt(m: types.Message, state: FSMContext):
    cancel_reminder_timer(m.from_user.id)
    data = await state.get_data()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{m.from_user.id}_{data['t_id']}_{data['price']}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{m.from_user.id}")]
    ])
    
    await bot_main.send_photo(ADMIN_ID, photo=m.photo[-1].file_id, caption=f"📸 <b>РУЧНАЯ ОПЛАТА</b>\nОт: {get_user_mention(m.from_user)}\nТариф ID: {data['t_id']}\nСумма: ${data['price']:.2f}", reply_markup=kb, parse_mode="HTML")
    await m.answer(TEXTS["en"]["custom_pay_sent"])
    await state.clear()

@dp.message(UserStates.custom_receipt)
async def custom_pay_not_photo(m: types.Message):
    await m.answer("❌ Please send a PHOTO (screenshot) of the receipt.", reply_markup=get_cancel_kb())

# --- ОДОБРЕНИЕ/ОТКЛОНЕНИЕ АДМИНОМ ---
@dp.callback_query(F.data.startswith("approve_"))
async def admin_approve(c: types.CallbackQuery):
    _, u_id, t_id, price = c.data.split("_")
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT INTO purchase_history (user_id, item_name, price_stars, price_crypto) VALUES (?, ?, 0, ?)", (int(u_id), f"Tariff {t_id} (Manual)", float(price)))
        await db.commit()
    
    try: await bot_main.send_message(int(u_id), TEXTS["en"]["custom_pay_approved"])
    except Exception: pass
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.reply("✅ Одобрено и выдано юзеру.")

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(c: types.CallbackQuery):
    u_id = int(c.data.split("_")[1])
    try: await bot_main.send_message(u_id, TEXTS["en"]["custom_pay_rejected"])
    except Exception: pass
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.reply("❌ Отклонено.")


# ==========================================
# ⚙️ АДМИН ПАНЕЛЬ
# ==========================================
@dp.callback_query(F.data == "admin_panel")
async def admin_panel_inline(c: types.CallbackQuery):
    if c.from_user.id == ADMIN_ID: 
        await c.message.edit_text("🎛 Панель Администратора", reply_markup=get_admin_main())

@dp.callback_query(F.data == "adm_back_to_main")
async def back_to_main(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("🎛 Панель Администратора", reply_markup=get_admin_main())

# -- ДОБАВИТЬ КАТЕГОРИЮ --
@dp.callback_query(F.data == "adm_add_cat")
async def add_cat(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("Введите название категории (будет показано всем):")
    await state.set_state(AdminStates.cat_name)

@dp.message(AdminStates.cat_name)
async def save_cat(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT INTO categories (name) VALUES (?)", (m.text.strip(),))
        await db.commit()
    await m.answer("✅ Категория создана!")
    welcome_text = await get_custom_text("welcome")
    await m.answer(welcome_text, reply_markup=await get_main_menu_inline(m.from_user.id))
    await state.clear()

# -- УДАЛИТЬ КАТЕГОРИЮ И ВСЕ ТАРИФЫ В НЕЙ --
@dp.callback_query(F.data == "adm_del_cat_start")
async def del_cat_start(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cur: cats = await cur.fetchall()
    kb = [[InlineKeyboardButton(text=f"🗑 {cat[1]}", callback_data=f"adm_delcat_{cat[0]}")] for cat in cats]
    kb.append([InlineKeyboardButton(text="Назад", callback_data="adm_back_to_main")])
    await c.message.edit_text("ВНИМАНИЕ! Выберите категорию для удаления. Все тарифы внутри также будут удалены:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_delcat_"))
async def del_cat_finish(c: types.CallbackQuery):
    c_id = int(c.data.split("_")[2])
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (c_id,))
        await db.execute("DELETE FROM tariffs WHERE category_id = ?", (c_id,))
        await db.commit()
    await c.message.edit_text("✅ Категория и все её тарифы удалены.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="adm_back_to_main")]]))

# -- ДОБАВИТЬ ТАРИФ --
@dp.callback_query(F.data == "adm_add_tariff")
async def add_tariff(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cur: cats = await cur.fetchall()
    if not cats: return await c.answer("Сначала создайте категорию!")
    kb = [[InlineKeyboardButton(text=cat[1], callback_data=f"adm_tcat_{cat[0]}")] for cat in cats]
    kb.append([InlineKeyboardButton(text="Отмена", callback_data="adm_back_to_main")])
    await c.message.edit_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_tcat_"))
async def add_t_name(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(cat_id=int(c.data.split("_")[2]))
    await c.message.edit_text("1/4. Введите НАЗВАНИЕ тарифа:")
    await state.set_state(AdminStates.t_name)

@dp.message(AdminStates.t_name)
async def add_t_desc(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    await m.answer("2/4. Введите ОПИСАНИЕ (поддерживается HTML):")
    await state.set_state(AdminStates.t_desc)

@dp.message(AdminStates.t_desc)
async def add_t_stars(m: types.Message, state: FSMContext):
    await state.update_data(desc=m.text.strip())
    await m.answer("3/4. Введите цену в STARS (целое число):")
    await state.set_state(AdminStates.t_stars)

@dp.message(AdminStates.t_stars)
async def add_t_crypto(m: types.Message, state: FSMContext):
    if not m.text.isdigit(): return
    await state.update_data(stars=int(m.text))
    await m.answer("4/4. Введите цену в USD:")
    await state.set_state(AdminStates.t_crypto)

@dp.message(AdminStates.t_crypto)
async def add_t_finish(m: types.Message, state: FSMContext):
    try: price_usd = float(m.text.replace(",", "."))
    except ValueError: return
    d = await state.get_data()
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT INTO tariffs (category_id, name, price_stars, price_crypto, description) VALUES (?,?,?,?,?)", (d['cat_id'], d['name'], d['stars'], price_usd, d['desc']))
        await db.commit()
    await m.answer("✅ Тариф сохранен!")
    welcome_text = await get_custom_text("welcome")
    await m.answer(welcome_text, reply_markup=await get_main_menu_inline(m.from_user.id))
    await state.clear()

# -- УДАЛИТЬ ТАРИФ --
@dp.callback_query(F.data == "adm_del_tariff_start")
async def del_t_start(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cur: cats = await cur.fetchall()
    kb = [[InlineKeyboardButton(text=cat[1], callback_data=f"adm_dtcat_{cat[0]}")] for cat in cats]
    kb.append([InlineKeyboardButton(text="Назад", callback_data="adm_back_to_main")])
    await c.message.edit_text("Выберите категорию для удаления тарифа:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_dtcat_"))
async def del_t_list(c: types.CallbackQuery):
    c_id = int(c.data.split("_")[2])
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT id, name FROM tariffs WHERE category_id = ?", (c_id,)) as cur: tariffs = await cur.fetchall()
    kb = [[InlineKeyboardButton(text=f"🗑 {t[1]}", callback_data=f"adm_dt_{t[0]}")] for t in tariffs]
    kb.append([InlineKeyboardButton(text="Назад", callback_data="adm_back_to_main")])
    await c.message.edit_text("Выберите тариф для УДАЛЕНИЯ:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_dt_"))
async def del_t_finish(c: types.CallbackQuery):
    t_id = int(c.data.split("_")[2])
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("DELETE FROM tariffs WHERE id = ?", (t_id,))
        await db.commit()
    await c.message.edit_text("✅ Тариф удален.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="adm_back_to_main")]]))

# -- ИЗМЕНИТЬ ЦЕНУ --
@dp.callback_query(F.data == "adm_edit_tariff_start")
async def edit_t_start(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cur: cats = await cur.fetchall()
    kb = [[InlineKeyboardButton(text=cat[1], callback_data=f"adm_etcat_{cat[0]}")] for cat in cats]
    kb.append([InlineKeyboardButton(text="Назад", callback_data="adm_back_to_main")])
    await c.message.edit_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_etcat_"))
async def edit_t_list(c: types.CallbackQuery):
    c_id = int(c.data.split("_")[2])
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT id, name FROM tariffs WHERE category_id = ?", (c_id,)) as cur: tariffs = await cur.fetchall()
    kb = [[InlineKeyboardButton(text=f"✏️ {t[1]}", callback_data=f"adm_et_{t[0]}")] for t in tariffs]
    kb.append([InlineKeyboardButton(text="Назад", callback_data="adm_back_to_main")])
    await c.message.edit_text("Выберите тариф:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_et_"))
async def edit_t_ask(c: types.CallbackQuery, state: FSMContext):
    t_id = int(c.data.split("_")[2])
    await state.update_data(t_id=t_id)
    await state.set_state(AdminStates.edit_price)
    await c.message.edit_text("Введите новые цены в формате: `STARS ПРОБЕЛ USD`\nПример: `150 5.50`", parse_mode="Markdown")

@dp.message(AdminStates.edit_price)
async def edit_t_finish(m: types.Message, state: FSMContext):
    try:
        parts = m.text.strip().split()
        stars, usd = int(parts[0]), float(parts[1].replace(",", "."))
    except Exception: return await m.answer("❌ Ошибка формата. Попробуйте еще раз: `150 5.50`", parse_mode="Markdown")
    
    t_id = (await state.get_data())['t_id']
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("UPDATE tariffs SET price_stars = ?, price_crypto = ? WHERE id = ?", (stars, usd, t_id))
        await db.commit()
    await m.answer("✅ Цены обновлены!")
    await state.clear()

# -- ТЕКСТЫ И КНОПКИ --
@dp.callback_query(F.data == "adm_manage_texts")
async def adm_texts(c: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="📝 Приветствие", callback_data="edittxt_welcome")],
        [InlineKeyboardButton(text="📝 Оплата", callback_data="edittxt_payment_title")],
        [InlineKeyboardButton(text="📝 Поддержка", callback_data="edittxt_support")], 
        [InlineKeyboardButton(text="📝 Отзывы", callback_data="edittxt_reviews")],
        [InlineKeyboardButton(text="🔘 Кнопка 'Купить'", callback_data="edittxt_btn_buy")],
        [InlineKeyboardButton(text="🔘 Кнопка 'Профиль'", callback_data="edittxt_btn_profile")],
        [InlineKeyboardButton(text="🔘 Кнопка 'Поддержка'", callback_data="edittxt_btn_support")],
        [InlineKeyboardButton(text="🔘 Кнопка 'Отзывы'", callback_data="edittxt_btn_reviews")],
        [InlineKeyboardButton(text="Назад", callback_data="adm_back_to_main")]
    ]
    await c.message.edit_text("Выберите текст для изменения (в тексте оплаты оставьте {name} для подстановки тарифа):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("edittxt_"))
async def adm_req_text(c: types.CallbackQuery, state: FSMContext):
    target_key = c.data.replace("edittxt_", "")
    await state.update_data(target_key=target_key)
    await c.message.edit_text("Отправьте новый текст (можно HTML, пишите на английском, так как интерфейс для юзеров англ.):")
    await state.set_state(AdminStates.edit_text)

@dp.message(AdminStates.edit_text)
async def adm_save_text(m: types.Message, state: FSMContext):
    d = await state.get_data()
    await update_custom_text(d['target_key'], m.text)
    await m.answer("✅ Текст обновлен!")
    await state.clear()

# -- НАСТРОЙКА АВТО-УВЕДОМЛЕНИЙ --
@dp.callback_query(F.data == "adm_auto_remind")
async def adm_auto_remind(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("Введите ПРОЦЕНТ скидки, который будет даваться юзеру, если он ничего не купил за 10 мин (например: 15):")
    await state.set_state(AdminStates.auto_remind_pct)

@dp.message(AdminStates.auto_remind_pct)
async def adm_auto_remind_pct(m: types.Message, state: FSMContext):
    try: pct = float(m.text.replace(",", "."))
    except: return await m.answer("Введите число!")
    await state.update_data(pct=pct)
    await m.answer("Отправьте ТЕКСТ сообщения. Обязательно используйте {percent} для вставки скидки и {code} для вставки сгенерированного промокода.\nПример: `Hey! Get a {percent}% discount using promo code {code}`", parse_mode="Markdown")
    await state.set_state(AdminStates.auto_remind_text)

@dp.message(AdminStates.auto_remind_text)
async def adm_auto_remind_finish(m: types.Message, state: FSMContext):
    d = await state.get_data()
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("UPDATE system_settings SET val = ? WHERE key = 'auto_remind_percent'", (str(d['pct']),))
        await db.execute("UPDATE system_settings SET val = ? WHERE key = 'auto_remind_text'", (m.text,))
        await db.commit()
    await m.answer("✅ Авто-уведомление настроено!")
    await state.clear()

# -- КАСТОМНЫЕ ПЛАТЕЖИ --
@dp.callback_query(F.data == "adm_manage_payments")
async def adm_pays(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT id, title FROM custom_payment_methods") as cur: pms = await cur.fetchall()
    kb = [[InlineKeyboardButton(text=f"🗑 {p[1]}", callback_data=f"adm_delpm_{p[0]}")] for p in pms]
    kb.append([InlineKeyboardButton(text="➕ Добавить способ", callback_data="adm_add_custpay")])
    kb.append([InlineKeyboardButton(text="Назад", callback_data="adm_back_to_main")])
    await c.message.edit_text("Управление способами оплаты (нажмите для удаления):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "adm_add_custpay")
async def adm_add_pm(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("Введите название кнопки (например: `Bank Transfer`):", parse_mode="Markdown")
    await state.set_state(AdminStates.pm_title)

@dp.message(AdminStates.pm_title)
async def adm_add_pm_instr(m: types.Message, state: FSMContext):
    await state.update_data(title=m.text)
    await m.answer("Введите инструкцию/реквизиты (например: `Send $ to card 1234`):", parse_mode="Markdown")
    await state.set_state(AdminStates.pm_instruction)

@dp.message(AdminStates.pm_instruction)
async def adm_add_pm_finish(m: types.Message, state: FSMContext):
    d = await state.get_data()
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT INTO custom_payment_methods (title, instruction) VALUES (?, ?)", (d['title'], m.text))
        await db.commit()
    await m.answer("✅ Способ добавлен!")
    await state.clear()

@dp.callback_query(F.data.startswith("adm_delpm_"))
async def adm_del_pm(c: types.CallbackQuery):
    pm_id = int(c.data.split("_")[2])
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("DELETE FROM custom_payment_methods WHERE id = ?", (pm_id,))
        await db.commit()
    await c.message.edit_text("✅ Удалено.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="adm_back_to_main")]]))

# -- ПРОМОКОДЫ --
@dp.callback_query(F.data == "adm_promos")
async def adm_promos(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT code, discount FROM promo_codes") as cur: promos = await cur.fetchall()
    kb = [[InlineKeyboardButton(text=f"🗑 {p[0]} ({p[1]}%)", callback_data=f"adm_delpromo_{p[0]}")] for p in promos]
    kb.append([InlineKeyboardButton(text="➕ Добавить промокод", callback_data="adm_add_promo")])
    kb.append([InlineKeyboardButton(text="Назад", callback_data="adm_back_to_main")])
    await c.message.edit_text("Промокоды (нажмите для удаления):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "adm_add_promo")
async def adm_add_pr(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("Введите код (Например: SALE50):")
    await state.set_state(AdminStates.promo_code)

@dp.message(AdminStates.promo_code)
async def adm_add_pr_disc(m: types.Message, state: FSMContext):
    await state.update_data(code=m.text.strip().upper())
    await m.answer("Введите ПРОЦЕНТ скидки (Например: 15 для 15%):")
    await state.set_state(AdminStates.promo_discount)

@dp.message(AdminStates.promo_discount)
async def adm_add_pr_finish(m: types.Message, state: FSMContext):
    try: disc = float(m.text.replace(",", "."))
    except: return await m.answer("Пожалуйста, введите число.")
    code = (await state.get_data())['code']
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT OR REPLACE INTO promo_codes (code, discount) VALUES (?, ?)", (code, disc))
        await db.commit()
    await m.answer("✅ Промокод добавлен!")
    await state.clear()

@dp.callback_query(F.data.startswith("adm_delpromo_"))
async def adm_del_pr(c: types.CallbackQuery):
    code = c.data.split("_")[2]
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("DELETE FROM promo_codes WHERE code = ?", (code,))
        await db.commit()
    await c.message.edit_text("✅ Удалено.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="В меню", callback_data="adm_back_to_main")]]))

# -- РАССЫЛКА --
@dp.callback_query(F.data == "adm_broadcast")
async def adm_bcast(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("Отправьте сообщение для рассылки (текст/фото/видео):")
    await state.set_state(AdminStates.broadcast_msg)

@dp.message(AdminStates.broadcast_msg)
async def adm_bcast_do(m: types.Message, state: FSMContext):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT user_id FROM users") as cur: users = await cur.fetchall()
    
    count, err = 0, 0
    await m.answer("⏳ Рассылка начата...")
    for u in users:
        try:
            await m.copy_to(u[0])
            count += 1
            await asyncio.sleep(0.05)
        except: err += 1
    
    await m.answer(f"✅ Рассылка завершена!\nУспешно: {count}\nОшибок: {err}")
    await state.clear()

# -- СТАТИСТИКА И CSV --
@dp.callback_query(F.data == "adm_stats")
async def adm_stats(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur: u_count = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*), SUM(price_stars), SUM(price_crypto) FROM purchase_history") as cur: p_data = await cur.fetchone()
    
    p_count = p_data[0] or 0
    s_stars = p_data[1] or 0
    s_usd = p_data[2] or 0.0
    
    text = f"📊 <b>Статистика бота</b>\n\n👥 Пользователей: {u_count}\n📦 Всего покупок: {p_count}\n\n💰 Доход (Stars): {s_stars} XTR\n💵 Доход (USD): ${s_usd:.2f}"
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="adm_back_to_main")]]))

@dp.callback_query(F.data == "adm_export")
async def adm_csv(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM purchase_history") as cur: data = await cur.fetchall()
    
    if not data: return await c.answer("Покупок еще нет!", show_alert=True)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID Покупки", "ID Юзера", "Товар", "Цена (Stars)", "Цена (USD)", "Дата"])
    writer.writerows(data)
    
    file = types.BufferedInputFile(output.getvalue().encode('utf-8'), filename="sales.csv")
    await c.message.answer_document(file, caption="📥 Выгрузка продаж")


async def main():
    await init_db()
    
    await bot_main.delete_webhook(drop_pending_updates=True)
    await bot_pay.delete_webhook(drop_pending_updates=True)
    
    await dp.start_polling(bot_main, bot_pay)

if __name__ == "__main__":
    asyncio.run(main())