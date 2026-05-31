import asyncio
import logging
import os
import csv
import io
import traceback
import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery, ErrorEvent

# --- КОНФИГ ---
CUSTOM_BOT_TOKEN = "" 
BOT_TOKEN = CUSTOM_BOT_TOKEN or os.getenv("BOT_TOKEN")
ADMIN_ID =   # ВСТАВЬТЕ СВОЙ REAL TELEGRAM ID СЮДА

# ТОКЕН ДЛЯ АВТОПРОВЕРКИ ЧЕКОВ
CRYPTO_BOT_TOKEN = "ВАШ_ТОКЕН_CRYPTO_BOT"  

# URL вашего Mini App (Web App)
WEB_APP_URL = "https://core.telegram.org/bots/webapps" # Замените на ссылку вашего магазина

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

logging.basicConfig(level=logging.INFO)

# --- ТЕКСТЫ ИНТЕРФЕЙСА ---
TEXTS = {
    "ru": {
        "welcome": "👋 Добро пожаловать! Выберите раздел меню:",
        "btn_buy": "💎 Купить тариф",
        "btn_support": "👨‍💻 Поддержка",
        "btn_reviews": "⭐ Отзывы",
        "btn_profile": "👤 Личный кабинет",
        "btn_webapp": "🌐 Web Store",
        "btn_admin": "⚙️ Admin Panel",
        "no_cats": "😔 Нет доступных категорий тарифов.",
        "select_cat": "📁 Выберите интересующую категорию:",
        "no_tariffs": "В этой категории пока нет тарифов.",
        "select_tariff": "📊 Категория <b>{name}</b>. Выберите тариф:",
        "back_to_cats": "⬅️ Назад к категориям",
        "back_to_tariffs": "⬅️ Назад к тарифам",
        "tariff_not_found": "Тариф не найден.",
        "payment_title": "💳 Оплата тарифа: <b>{name}</b>\nВыберите удобный способ:",
        "stars_btn": "🌟 Telegram Stars ({stars} XTR)",
        "crypto_btn": "⚡ CryptoBot (${price})",
        "stars_invoice_title": "Оплата тарифа {name}",
        "stars_invoice_desc": "Получение доступа к тарифу {name}",
        "invoice_error": "❌ Ошибка при генерации счета. Напишите в поддержку.",
        "success_pay_stars": "🎉 Спасибо за покупку! Оплата успешно принята, ваш тариф активирован.",
        "crypto_instruction": "🤖 Создайте чек на сумму <b>${price}</b> в боте @CryptoBot и отправьте ссылку сюда в чат.",
        "crypto_bad_link": "❌ Ссылка не распознана как чек. Пожалуйста, отправьте корректную ссылку на чек:",
        "crypto_success": "🎉 Ваш чек отправлен администрации на проверку! Ожидайте активации.",
        "crypto_auto_success": "✅ Чек успешно проверен автоматически! Сумма ${amount} зачислена. Тариф активирован!",
        "crypto_auto_fail": "❌ Не удалось автоматически проверить чек (возможно, он уже активирован). Чек передан админу на ручную проверку.",
        "promo_btn": "🎟 Ввести промокод",
        "promo_success": "✅ Промокод применен! Новая цена: <b>${price}</b>",
        "promo_not_found": "❌ Промокод не найден или исчез.",
        "custom_pay_prompt": "📸 Пожалуйста, отправьте <b>скриншот или фото чека</b> об оплате в этот чат. Администрация проверит его в ближайшее время.",
        "custom_pay_sent": "⏳ Ваш чек успешно отправлен администрации на проверку! Мы уведомим вас об активации.",
        "custom_pay_approved": "🎉 Администратор одобрил ваш платеж! Тариф активирован. Спасибо за покупку!",
        "custom_pay_rejected": "❌ Ваш платеж был отклонен администрацией. Если это ошибка, свяжитесь с поддержкой."
    },
    "en": {
        "welcome": "👋 Welcome! Choose a section below:",
        "btn_buy": "💎 Buy Tariff",
        "btn_support": "👨‍💻 Support",
        "btn_reviews": "⭐ Reviews",
        "btn_profile": "👤 Profile",
        "btn_webapp": "🌐 Web Store",
        "btn_admin": "⚙️ Admin Panel",
        "no_cats": "😔 No active categories available.",
        "select_cat": "📁 Select a category you are interested in:",
        "no_tariffs": "There are no tariffs in this category yet.",
        "select_tariff": "📊 Category <b>{name}</b>. Select a tariff:",
        "back_to_cats": "⬅️ Back to categories",
        "back_to_tariffs": "⬅️ Back to tariffs",
        "tariff_not_found": "Tariff not found.",
        "payment_title": "💳 Payment for tariff: <b>{name}</b>\nChoose a convenient method:",
        "stars_btn": "🌟 Telegram Stars ({stars} XTR)",
        "crypto_btn": "⚡ CryptoBot (${price})",
        "stars_invoice_title": "Payment for tariff {name}",
        "stars_invoice_desc": "Getting access to tariff {name}",
        "invoice_error": "❌ Error generating invoice. Please contact support.",
        "success_pay_stars": "🎉 Thank you for your purchase! Payment successfully accepted, your tariff is activated.",
        "crypto_instruction": "🤖 Create a cheque for <b>${price}</b> in @CryptoBot and send the link here in the chat.",
        "crypto_bad_link": "❌ Link not recognized as a cheque. Please send a valid cheque link:",
        "crypto_success": "🎉 Your cheque has been sent to administration for verification! Awaiting activation.",
        "crypto_auto_success": "✅ Cheque verified automatically! Amount of ${amount} received. Tariff activated!",
        "crypto_auto_fail": "❌ Automatic verification failed (cheque may be used or invalid). Sent to admin manually.",
        "promo_btn": "🎟 Use Promo Code",
        "promo_success": "✅ Promo code applied! New price: <b>${price}</b>",
        "promo_not_found": "❌ Promo code not found or expired.",
        "custom_pay_prompt": "📸 Please send a <b>screenshot or photo of your receipt</b> to this chat. The administration will verify it shortly.",
        "custom_pay_sent": "⏳ Your receipt has been successfully sent to the admin for verification! We will notify you once it is activated.",
        "custom_pay_approved": "🎉 The administrator has approved your payment! Tariff activated. Thank you for your purchase!",
        "custom_pay_rejected": "❌ Your payment was rejected by the administration. If this is a mistake, please contact support."
    }
}

# --- ИНИЦИАЛИЗАЦИЯ БД (aiosqlite) ---
async def init_db():
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT 'ru', balance REAL DEFAULT 0.0)")
        await db.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS tariffs (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, price_stars INTEGER, price_crypto REAL)")
        await db.execute("CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, val_ru TEXT, val_en TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS custom_payment_methods (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, instruction TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, discount REAL)")
        await db.execute("CREATE TABLE IF NOT EXISTS purchase_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, price_stars INTEGER, price_crypto REAL, date TEXT DEFAULT CURRENT_TIMESTAMP)")
        
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val_ru, val_en) VALUES ('support', '📝 Связь с менеджером: @ваша_поддержка', '📝 Contact manager: @your_support')")
        await db.execute("INSERT OR IGNORE INTO system_settings (key, val_ru, val_en) VALUES ('reviews', '💬 Читайте отзывы в нашем канале: [Ссылка]', '💬 Read reviews in our channel: [Link]')")
        await db.commit()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def get_user_lang(user_id: int):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "ru"

async def get_custom_text(key: str, lang: str):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT val_ru, val_en FROM system_settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            if row: return row[0] if lang == "ru" else row[1]
    return "Not found"

async def update_custom_text(key: str, lang: str, new_text: str):
    async with aiosqlite.connect("tariffs.db") as db:
        if lang == "ru": 
            await db.execute("UPDATE system_settings SET val_ru = ? WHERE key = ?", (new_text, key))
        else: 
            await db.execute("UPDATE system_settings SET val_en = ? WHERE key = ?", (new_text, key))
        await db.commit()

def parse_multilang_text(text: str, lang: str):
    if not text: return "Без названия"
    if " / " in text:
        parts = text.split(" / ")
        return parts[0].strip() if lang == "ru" else parts[1].strip()
    return text

def get_user_mention(user: types.User) -> str:
    if user.username: return f"@{user.username} (ID: {user.id})"
    return f"<a href='tg://user?id={user.id}'>{user.full_name}</a> (ID: {user.id})"

async def notify_admin(action_text: str):
    try: await bot.send_message(ADMIN_ID, f"👁 <b>Лог действий:</b>\n{action_text}", parse_mode="HTML")
    except Exception as e: print(f"[Ошибка уведомлений] Не удалось отправить лог админу: {e}")

# ОБРАБОТЧИК КНОПОК ДЛЯ ЛОГИРОВАНИЯ
@dp.callback_query.middleware
async def log_callback_middleware(handler, event: types.CallbackQuery, data):
    if event.from_user.id != ADMIN_ID:
        user_info = get_user_mention(event.from_user)
        await notify_admin(f"👤 Пользователь {user_info}\n🔘 Нажал кнопку: <code>{event.data}</code>")
    return await handler(event, data)

async def verify_cryptobot_check(check_id: str) -> dict:
    if not CRYPTO_BOT_TOKEN or CRYPTO_BOT_TOKEN == "ВАШ_ТОКЕН_CRYPTO_BOT":
        return {"status": "no_token"}
    
    base_url = "https://pay.cryptobot.pay/api/getChecks"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(base_url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("ok") and data.get("result"):
                        for c in data["result"]:
                            if str(c.get("check_id")) == str(check_id) or check_id in c.get("bot_check_url", ""):
                                return {"status": c.get("status"), "amount": float(c.get("amount")), "asset": c.get("asset")}
        except Exception as e:
            logging.error(f"CryptoBot API Error: {e}")
    return {"status": "error"}

# --- FSM СОСТОЯНИЯ ---
class AdminStates(StatesGroup):
    waiting_for_cat_name = State()
    waiting_for_t_name = State()
    waiting_for_t_stars = State()
    waiting_for_t_crypto = State()
    waiting_for_edit_text = State()
    waiting_for_pm_title = State()       
    waiting_for_pm_instruction = State() 
    waiting_for_broadcast_msg = State() 
    waiting_for_promo_code = State()    
    waiting_for_promo_discount = State()

class UserStates(StatesGroup):
    waiting_for_check = State()
    waiting_for_promo_apply = State()   
    waiting_for_custom_receipt = State()

# --- СИСТЕМА КЛАВИАТУР ---
async def get_main_menu(user_id: int):
    lang = await get_user_lang(user_id)
    kb = [
        [types.KeyboardButton(text=TEXTS[lang]["btn_buy"])],
        [types.KeyboardButton(text=TEXTS[lang]["btn_webapp"], web_app=types.WebAppInfo(url=WEB_APP_URL))],
        [types.KeyboardButton(text=TEXTS[lang]["btn_profile"])],
        [types.KeyboardButton(text=TEXTS[lang]["btn_support"]), types.KeyboardButton(text=TEXTS[lang]["btn_reviews"])]
    ]
    if user_id == ADMIN_ID:
        kb.append([types.KeyboardButton(text="⚙️ Админ Панель")])
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_admin_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 Создать Категорию", callback_data="adm_add_cat"), InlineKeyboardButton(text="➕ Добавить Тариф", callback_data="adm_add_tariff")],
        [InlineKeyboardButton(text="🗑 Удалить Тариф", callback_data="adm_del_tariff_start"), InlineKeyboardButton(text="📝 Тексты Кнопок", callback_data="adm_manage_texts")],
        [InlineKeyboardButton(text="💳 Способы Оплаты", callback_data="adm_manage_payments"), InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="adm_promos"), InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="📥 Выгрузить продажи (CSV)", callback_data="adm_export")],
        [InlineKeyboardButton(text="❌ Выход", callback_data="adm_exit")]
    ])

# =====================================================================
# 👤 ЛОГИКА ПОЛЬЗОВАТЕЛЯ
# =====================================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user_exists = await cursor.fetchone()
        
        if not user_exists:
            await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()

    user_info = get_user_mention(message.from_user)
    if user_id != ADMIN_ID:
        await notify_admin(f"👤 Пользователь {user_info}\n▶️ Запустил бота.")
        
    await message.answer("🇷🇺 Выберите язык / 🇬🇧 Choose language:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")]
    ]))

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, callback.from_user.id))
        await db.commit()
    
    main_menu = await get_main_menu(callback.from_user.id)
    await callback.message.answer(TEXTS[lang]["welcome"], reply_markup=main_menu)
    await callback.answer()

@dp.message(F.text.in_({"👤 Личный кабинет", "👤 Profile"}))
async def show_profile(message: types.Message):
    lang = await get_user_lang(message.from_user.id)
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT item_name, price_crypto, date FROM purchase_history WHERE user_id = ? ORDER BY id DESC LIMIT 5", (message.from_user.id,)) as cursor:
            history = await cursor.fetchall()
    
    history_text = ""
    if history:
        for item in history:
            history_text += f"▪️ {item[0]} (${item[1]}) — {item[2]}\n"
    else:
        history_text = "История покупок пуста / Purchase history is empty"

    text_ru = f"👤 <b>Личный кабинет</b>\n\n🆔 Ваш ID: <code>{message.from_user.id}</code>\n\n<b>Последние покупки:</b>\n{history_text}"
    text_en = f"👤 <b>Profile</b>\n\n🆔 Your ID: <code>{message.from_user.id}</code>\n\n<b>Recent Purchases:</b>\n{history_text}"
    await message.answer(text_ru if lang == "ru" else text_en, parse_mode="HTML")

@dp.message(F.text.in_({"👨‍💻 Поддержка", "👨‍💻 Support"}))
async def show_support(message: types.Message):
    lang = await get_user_lang(message.from_user.id)
    text = await get_custom_text("support", lang)
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text.in_({"⭐ Отзывы", "⭐ Reviews"}))
async def show_reviews(message: types.Message):
    lang = await get_user_lang(message.from_user.id)
    text = await get_custom_text("reviews", lang)
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text.in_({"💎 Купить тариф", "💎 Buy Tariff"}))
async def buy_tariff(message: types.Message):
    lang = await get_user_lang(message.from_user.id)
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cursor:
            categories = await cursor.fetchall()

    if not categories:
        await message.answer(TEXTS[lang]["no_cats"])
        return

    inline_kb = [[InlineKeyboardButton(text=parse_multilang_text(cat[1], lang), callback_data=f"cat_{cat[0]}")] for cat in categories]
    await message.answer(TEXTS[lang]["select_cat"], reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb))

@dp.callback_query(F.data == "back_to_cats")
async def back_to_cats_cb(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cursor:
            categories = await cursor.fetchall()
            
    inline_kb = [[InlineKeyboardButton(text=parse_multilang_text(cat[1], lang), callback_data=f"cat_{cat[0]}")] for cat in categories]
    await callback.message.edit_text(TEXTS[lang]["select_cat"], reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def select_category(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    cat_id = int(callback.data.split("_")[1])
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)) as cursor:
            cat_row = await cursor.fetchone()
            if not cat_row: return
            cat_name = cat_row[0]
        async with db.execute("SELECT * FROM tariffs WHERE category_id = ?", (cat_id,)) as cursor:
            tariffs = await cursor.fetchall()

    if not tariffs:
        await callback.answer(TEXTS[lang]["no_tariffs"], show_alert=True)
        return

    inline_kb = [[InlineKeyboardButton(text=f"{parse_multilang_text(t[2], lang)} (${t[4]})", callback_data=f"select_{t[0]}")] for t in tariffs]
    inline_kb.append([InlineKeyboardButton(text=TEXTS[lang]["back_to_cats"], callback_data="back_to_cats")])
    await callback.message.edit_text(TEXTS[lang]["select_tariff"].format(name=parse_multilang_text(cat_name, lang)), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb))
    await callback.answer()

@dp.callback_query(F.data.startswith("select_"))
async def select_method(callback: types.CallbackQuery, state: FSMContext):
    await state.clear() 
    lang = await get_user_lang(callback.from_user.id)
    t_id = int(callback.data.split("_")[1])
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM tariffs WHERE id = ?", (t_id,)) as cursor:
            t = await cursor.fetchone()
        async with db.execute("SELECT id, title FROM custom_payment_methods") as cursor:
            custom_methods = await cursor.fetchall()

    if not t: return
    t_name = parse_multilang_text(t[2], lang)
    
    inline_keyboard = [
        [InlineKeyboardButton(text=TEXTS[lang]["stars_btn"].format(stars=t[3]), callback_data=f"stars_{t[0]}")],
        [InlineKeyboardButton(text=TEXTS[lang]["crypto_btn"].format(price=t[4]), callback_data=f"crypto_{t[0]}")],
        [InlineKeyboardButton(text=TEXTS[lang]["promo_btn"], callback_data=f"applypromo_{t[0]}")] 
    ]
    for cm in custom_methods:
        inline_keyboard.append([InlineKeyboardButton(text=parse_multilang_text(cm[1], lang), callback_data=f"custpay_{cm[0]}_{t[0]}")])
    inline_keyboard.append([InlineKeyboardButton(text=TEXTS[lang]["back_to_tariffs"], callback_data=f"cat_{t[1]}")])
    
    await callback.message.edit_text(TEXTS[lang]["payment_title"].format(name=t_name), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_keyboard))
    await callback.answer()

@dp.callback_query(F.data.startswith("applypromo_"))
async def user_apply_promo_start(callback: types.CallbackQuery, state: FSMContext):
    t_id = int(callback.data.split("_")[1])
    await state.update_data(t_id=t_id)
    await state.set_state(UserStates.waiting_for_promo_apply)
    await callback.message.answer("🎟 Отправьте промокод в чат / Send promo code here:")
    await callback.answer()

@dp.message(UserStates.waiting_for_promo_apply)
async def user_apply_promo_finish(message: types.Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    code = message.text.strip().upper()
    data = await state.get_data()
    t_id = data['t_id']
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT discount FROM promo_codes WHERE code = ?", (code,)) as cursor:
            promo = await cursor.fetchone()
        async with db.execute("SELECT * FROM tariffs WHERE id = ?", (t_id,)) as cursor:
            t = await cursor.fetchone()
        async with db.execute("SELECT id, title FROM custom_payment_methods") as cursor:
            custom_methods = await cursor.fetchall()
    
    if not promo or not t:
        return await message.answer(TEXTS[lang]["promo_not_found"])
        
    discount = float(promo[0])
    new_price_crypto = max(0.0, float(t[4]) - discount)
    await state.update_data(discount=discount, promo_code=code)
    
    await message.answer(TEXTS[lang]["promo_success"].format(price=new_price_crypto), parse_mode="HTML")
    
    inline_keyboard = [
        [InlineKeyboardButton(text=TEXTS[lang]["crypto_btn"].format(price=new_price_crypto), callback_data=f"crypto_{t[0]}")],
    ]
    for cm in custom_methods:
        inline_keyboard.append([InlineKeyboardButton(text=parse_multilang_text(cm[1], lang), callback_data=f"custpay_{cm[0]}_{t[0]}")])
        
    await message.answer(TEXTS[lang]["payment_title"].format(name=parse_multilang_text(t[2], lang)), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_keyboard))

@dp.callback_query(F.data.startswith("custpay_"))
async def process_custom_payment_view(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_user_lang(callback.from_user.id)
    _, cm_id, t_id = callback.data.split("_")
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT title, instruction FROM custom_payment_methods WHERE id = ?", (int(cm_id),)) as cursor:
            cm = await cursor.fetchone()
        async with db.execute("SELECT name, price_crypto FROM tariffs WHERE id = ?", (int(t_id),)) as cursor:
            t = await cursor.fetchone()
    
    if not cm: return
    
    state_data = await state.get_data()
    final_price = max(0.0, float(t[1]) - state_data.get('discount', 0.0))
    
    await state.update_data(t_id=int(t_id), t_name=parse_multilang_text(t[0], lang), final_price=final_price, cm_title=parse_multilang_text(cm[0], lang))
    await state.set_state(UserStates.waiting_for_custom_receipt)
    
    text = f"💳 <b>{parse_multilang_text(cm[0], lang)}</b>\n\n{parse_multilang_text(cm[1], lang)}\n\n💰 К оплате с учетом скидок: <b>${final_price}</b>\n\n{TEXTS[lang]['custom_pay_prompt']}"
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.message(UserStates.waiting_for_custom_receipt, F.photo)
async def custom_receipt_received(message: types.Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"aprv_{message.from_user.id}_{data['t_id']}_{data['final_price']}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rjct_{message.from_user.id}")
        ]
    ])
    
    admin_text = (
        f"🔔 <b>НОВЫЙ КАСТОМНЫЙ ПЛАТЕЖ НА ПРОВЕРКУ!</b>\n\n"
        f"👤 От: {get_user_mention(message.from_user)}\n"
        f"⚙️ Способ: <b>{data['cm_title']}</b>\n"
        f"📊 Тариф: <b>{data['t_name']}</b>\n"
        f"💰 Сумма: <b>${data['final_price']}</b>"
    )
    
    await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_text, parse_mode="HTML", reply_markup=admin_kb)
    
    main_menu = await get_main_menu(message.from_user.id)
    await message.answer(TEXTS[lang]["custom_pay_sent"], reply_markup=main_menu)
    await state.clear()

@dp.callback_query(F.data.startswith("stars_"))
async def process_stars(callback: types.CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    t_id = int(callback.data.split("_")[1])
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM tariffs WHERE id = ?", (t_id,)) as cursor:
            t = await cursor.fetchone()

    t_name = parse_multilang_text(t[2], lang)
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=TEXTS[lang]["stars_invoice_title"].format(name=t_name),
            description=TEXTS[lang]["stars_invoice_desc"].format(name=t_name),
            payload=f"stars_pay_{t[0]}_{t[3]}",
            currency="XTR",
            prices=[LabeledPrice(label=t_name, amount=int(t[3]))]
        )
        await callback.answer()
    except Exception: 
        await callback.message.answer(TEXTS[lang]["invoice_error"])

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def success_pay(message: types.Message):
    lang = await get_user_lang(message.from_user.id)
    payload = message.successful_payment.invoice_payload.split("_")
    tariff_id = payload[2]
    amount = message.successful_payment.total_amount
    
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT INTO purchase_history (user_id, item_name, price_stars, price_crypto) VALUES (?, ?, ?, 0)", (message.from_user.id, f"Tariff ID: {tariff_id} (Stars)", amount))
        await db.commit()
    
    await notify_admin(f"💰 <b>УСПЕШНАЯ ОПЛАТА STARS!</b>\nПользователь: {get_user_mention(message.from_user)}\nСумма: {amount} XTR")
    await message.answer(TEXTS[lang]["success_pay_stars"])

@dp.callback_query(F.data.startswith("crypto_"))
async def process_crypto(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_user_lang(callback.from_user.id)
    t_id = int(callback.data.split("_")[1])
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM tariffs WHERE id = ?", (t_id,)) as cursor:
            t = await cursor.fetchone()

    state_data = await state.get_data()
    final_price = max(0.0, float(t[4]) - state_data.get('discount', 0.0))

    await state.update_data(t_name=parse_multilang_text(t[2], lang), t_price=final_price)
    await state.set_state(UserStates.waiting_for_check)
    await callback.message.answer(TEXTS[lang]["crypto_instruction"].format(price=final_price), parse_mode="HTML")
    await callback.answer()

@dp.message(UserStates.waiting_for_check)
async def check_received(message: types.Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    text = message.text.strip()
    if "t.me/CryptoBot?start=" not in text and "t.me/CryptoTestBot?start=" not in text:
        await message.answer(TEXTS[lang]["crypto_bad_link"])
        return
    
    data = await state.get_data()
    check_code = text.split("start=")[1]
    api_res = await verify_cryptobot_check(check_code)
    
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT INTO purchase_history (user_id, item_name, price_stars, price_crypto) VALUES (?, ?, 0, ?)", (message.from_user.id, data.get('t_name'), data.get('t_price')))
        await db.commit()

    main_menu = await get_main_menu(message.from_user.id)

    if api_res.get("status") in ["active", "completed"]:
        await message.answer(TEXTS[lang]["crypto_auto_success"].format(amount=api_res['amount']), reply_markup=main_menu)
        await notify_admin(f"🤖 <b>АВТО-АКТИВАЦИЯ ЧЕКА!</b>\nОт: {get_user_mention(message.from_user)}\nТариф: {data.get('t_name')} (${data.get('t_price')})")
    else:
        await notify_admin(f"🧾 <b>ПОЛУЧЕН ЧЕК CRYPTOBOT (РУЧНАЯ ПРОВЕРКА)!</b>\nОт: {get_user_mention(message.from_user)}\nТариф: <b>{data.get('t_name')}</b>\nСсылка: {text}")
        await message.answer(TEXTS[lang]["crypto_success"], reply_markup=main_menu)
    
    await state.clear()


# =====================================================================
# ⚙️ ПАНЕЛЬ АДМИНИСТРАТОРА
# =====================================================================

@dp.message(F.text == "⚙️ Админ Панель")
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🎛 Панель управления", reply_markup=get_admin_main())

@dp.callback_query(F.data.startswith("aprv_"))
async def admin_approve_receipt(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    _, user_id, t_id, price = c.data.split("_")
    user_id, t_id, price = int(user_id), int(t_id), float(price)
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT name FROM tariffs WHERE id = ?", (t_id,)) as cursor:
            t_row = await cursor.fetchone()
            t_name = t_row[0] if t_row else f"ID: {t_id}"
            
        await db.execute("INSERT INTO purchase_history (user_id, item_name, price_stars, price_crypto) VALUES (?, ?, 0, ?)", (user_id, t_name, price))
        await db.commit()
        
    user_lang = await get_user_lang(user_id)
    try: await bot.send_message(user_id, TEXTS[user_lang]["custom_pay_approved"])
    except Exception: pass
    
    await c.message.edit_caption(caption=c.message.caption + "\n\n🟢 <b>ОДОБРЕНО!</b>", reply_markup=None)
    await c.answer("Успешно одобрено!")

@dp.callback_query(F.data.startswith("rjct_"))
async def admin_reject_receipt(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    user_id = int(c.data.split("_")[1])
    
    user_lang = await get_user_lang(user_id)
    try: await bot.send_message(user_id, TEXTS[user_lang]["custom_pay_rejected"])
    except Exception: pass
    
    await c.message.edit_caption(caption=c.message.caption + "\n\n🔴 <b>ОТКЛОНЕНО!</b>", reply_markup=None)
    await c.answer("Платеж отклонен.")

@dp.callback_query(F.data == "adm_del_tariff_start")
async def adm_del_tariff_cats(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cursor:
            cats = await cursor.fetchall()
    if not cats:
        return await c.answer("Нет категорий для удаления тарифов!", show_alert=True)
    
    kb = [[InlineKeyboardButton(text=cat[1], callback_data=f"adm_delcat_{cat[0]}")] for cat in cats]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back_to_main")])
    await c.message.edit_text("🗑 Выберите категорию, из которой нужно удалить тариф:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_delcat_"))
async def adm_del_tariff_list(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    cat_id = int(c.data.split("_")[2])
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT id, name FROM tariffs WHERE category_id = ?", (cat_id,)) as cursor:
            tariffs = await cursor.fetchall()
        
    if not tariffs:
        return await c.answer("В этой категории нет тарифов!", show_alert=True)
        
    kb = [[InlineKeyboardButton(text=f"❌ {t[1]}", callback_data=f"adm_removet_{t[0]}_{cat_id}")] for t in tariffs]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_del_tariff_start")])
    await c.message.edit_text("Нажмите на тариф, чтобы БЕЗВОЗВРАТНО удалить его:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_removet_"))
async def adm_del_tariff_finish(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    
    parts = c.data.split("_")
    t_id = int(parts[2])
    cat_id = int(parts[3])
    
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("DELETE FROM tariffs WHERE id = ?", (t_id,))
        await db.commit()
    
    await c.answer("Тариф успешно удален!")

    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT id, name FROM tariffs WHERE category_id = ?", (cat_id,)) as cursor:
            tariffs = await cursor.fetchall()
        
    if not tariffs:
        await c.message.edit_text("В этой категории больше нет тарифов.", reply_markup=None)
        return
        
    kb = [[InlineKeyboardButton(text=f"❌ {t[1]}", callback_data=f"adm_removet_{t[0]}_{cat_id}")] for t in tariffs]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_del_tariff_start")])
    await c.message.edit_text("Тариф удален. Список обновлен:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "adm_exit")
async def adm_exit(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.delete()
    await c.answer()

@dp.callback_query(F.data == "adm_back_to_main")
async def back_to_main(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("🎛 Панель управления", reply_markup=get_admin_main())
    await c.answer()

@dp.callback_query(F.data == "adm_stats")
async def adm_show_stats(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT COUNT(user_id) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        async with db.execute("SELECT SUM(price_crypto) FROM purchase_history") as cursor:
            total_crypto = (await cursor.fetchone())[0] or 0.0
        async with db.execute("SELECT SUM(price_stars) FROM purchase_history") as cursor:
            total_stars = (await cursor.fetchone())[0] or 0
    
    stat_text = f"📊 <b>Статистика бота</b>\n\n👤 Всего пользователей в базе: {total_users}\n💰 Всего заработано (Crypto): <b>${total_crypto}</b>\n🌟 Всего заработано (Stars): <b>{total_stars} XTR</b>"
    await c.message.edit_text(stat_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back_to_main")]]))

@dp.callback_query(F.data == "adm_export")
async def adm_export_csv(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM purchase_history") as cursor:
            rows = await cursor.fetchall()
            
    if not rows:
        return await c.answer("История покупок пуста!", show_alert=True)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID транзакции", "ID пользователя", "Название товара", "Цена в Stars", "Цена в Crypto ($)", "Дата и время"])
    writer.writerows(rows)
    
    csv_bytes = output.getvalue().encode('utf-8')
    file = types.BufferedInputFile(csv_bytes, filename="sales_report.csv")
    
    await c.message.answer_document(document=file, caption="📊 Отчет о продажах выгружен.")
    await c.answer()

@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_start(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("📢 Отправьте текст рассылки (разрешен HTML):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_back_to_main")]]))
    await state.set_state(AdminStates.waiting_for_broadcast_msg)

@dp.message(AdminStates.waiting_for_broadcast_msg)
async def adm_broadcast_finish(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
    
    await m.answer(f"🚀 Начинаю рассылку на {len(users)} пользователей...")
    success = 0
    for u in users:
        try:
            await bot.send_message(u[0], m.text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05) 
        except Exception: pass
    await m.answer(f"✅ Рассылка завершена! Успешно доставлено: {success}/{len(users)}")
    await state.clear()

@dp.callback_query(F.data == "adm_promos")
async def adm_manage_promos(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM promo_codes") as cursor:
            promos = await cursor.fetchall()
    
    text = "🎟 <b>Управление промокодами</b>\n\nСписок активных кодов:\n"
    kb = [[InlineKeyboardButton(text="➕ Создать промокод", callback_data="adm_add_promo")]]
    for p in promos:
        text += f"▪️ <code>{p[0]}</code> — скидка ${p[1]}\n"
        kb.append([InlineKeyboardButton(text=f"❌ Удалить {p[0]}", callback_data=f"adm_del_promo_{p[0]}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back_to_main")])
    await c.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "adm_add_promo")
async def adm_add_promo_code(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("Введите код (Например: SALE10):")
    await state.set_state(AdminStates.waiting_for_promo_code)

@dp.message(AdminStates.waiting_for_promo_code)
async def adm_add_promo_discount(m: types.Message, state: FSMContext):
    await state.update_data(code=m.text.strip().upper())
    await m.answer("Введите сумму скидки в долларах USD (Например: 5):")
    await state.set_state(AdminStates.waiting_for_promo_discount)

@dp.message(AdminStates.waiting_for_promo_discount)
async def adm_add_promo_finish(m: types.Message, state: FSMContext):
    data = await state.get_data()
    try: discount = float(m.text.replace(",", "."))
    except ValueError: return await m.answer("Введите число!")
    
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT OR REPLACE INTO promo_codes (code, discount) VALUES (?, ?)", (data['code'], discount))
        await db.commit()
        
    main_menu = await get_main_menu(m.from_user.id)
    await m.answer("✅ Промокод успешно создан!", reply_markup=main_menu)
    await state.clear()

@dp.callback_query(F.data.startswith("adm_del_promo_"))
async def adm_del_promo(c: types.CallbackQuery):
    code = c.data.split("_")[3]
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("DELETE FROM promo_codes WHERE code = ?", (code,))
        await db.commit()
    await c.answer("Промокод удален!")
    await adm_manage_promos(c)

@dp.callback_query(F.data == "adm_add_cat")
async def add_cat_start(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("Введите название категории (Пример: <code>Яблоки / Apples</code>):", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_back_to_main")]]))
    await state.set_state(AdminStates.waiting_for_cat_name)

@dp.message(AdminStates.waiting_for_cat_name)
async def save_cat(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT INTO categories (name) VALUES (?)", (m.text.strip(),))
        await db.commit()
        
    main_menu = await get_main_menu(m.from_user.id)
    await m.answer(f"✅ Категория успешно создана!", reply_markup=main_menu)
    await state.clear()

@dp.callback_query(F.data == "adm_add_tariff")
async def add_tariff_start(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT * FROM categories") as cursor:
            cats = await cursor.fetchall()
            
    if not cats: return
    kb = [[InlineKeyboardButton(text=cat[1], callback_data=f"adm_tcat_{cat[0]}")] for cat in cats]
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="adm_back_to_main")])
    await c.message.edit_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("adm_tcat_"))
async def add_tariff_name(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(cat_id=int(c.data.split("_")[2]))
    await c.message.edit_text("Шаг [1/3]: Введите НАЗВАНИЕ тарифа (Пример: <code>Премиум / Premium</code>):", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_t_name)

@dp.message(AdminStates.waiting_for_t_name)
async def add_tariff_stars(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    await m.answer("Шаг [2/3]: Введите цену в Telegram Stars:")
    await state.set_state(AdminStates.waiting_for_t_stars)

@dp.message(AdminStates.waiting_for_t_stars)
async def add_tariff_crypto(m: types.Message, state: FSMContext):
    if not m.text.isdigit(): return
    await state.update_data(stars=int(m.text))
    await m.answer("Шаг [3/3]: Введите цену в USD для CryptoBot:")
    await state.set_state(AdminStates.waiting_for_t_crypto)

@dp.message(AdminStates.waiting_for_t_crypto)
async def add_tariff_finish(m: types.Message, state: FSMContext):
    try: price_usd = float(m.text.replace(",", "."))
    except ValueError: return
    data = await state.get_data()
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT INTO tariffs (category_id, name, price_stars, price_crypto) VALUES (?,?,?,?)", (int(data['cat_id']), str(data['name']), int(data['stars']), price_usd))
        await db.commit()
    await state.clear()
    
    main_menu = await get_main_menu(m.from_user.id)
    await m.answer(f"✅ Тариф успешно сохранен!", reply_markup=main_menu)

@dp.callback_query(F.data == "adm_manage_texts")
async def adm_manage_texts(c: types.CallbackQuery):
    kb = [[InlineKeyboardButton(text="🇷🇺 Поддержка", callback_data="edittxt_support_ru"), InlineKeyboardButton(text="🇬🇧 Support", callback_data="edittxt_support_en")], [InlineKeyboardButton(text="🇷🇺 Отзывы", callback_data="edittxt_reviews_ru"), InlineKeyboardButton(text="🇬🇧 Reviews", callback_data="edittxt_reviews_en")], [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back_to_main")]]
    await c.message.edit_text("Выберите текст:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("edittxt_"))
async def adm_request_new_text(c: types.CallbackQuery, state: FSMContext):
    _, target_key, target_lang = c.data.split("_")
    await state.update_data(target_key=target_key, target_lang=target_lang)
    await c.message.edit_text("Отправьте новое сообщение с текстом:")
    await state.set_state(AdminStates.waiting_for_edit_text)

@dp.message(AdminStates.waiting_for_edit_text)
async def adm_save_custom_text(m: types.Message, state: FSMContext):
    data = await state.get_data()
    await update_custom_text(data['target_key'], data['target_lang'], m.text)
    
    main_menu = await get_main_menu(m.from_user.id)
    await m.answer("✅ Изменения применены!", reply_markup=main_menu)
    await state.clear()

@dp.callback_query(F.data == "adm_manage_payments")
async def adm_manage_payments(c: types.CallbackQuery):
    async with aiosqlite.connect("tariffs.db") as db:
        async with db.execute("SELECT id, title FROM custom_payment_methods") as cursor:
            methods = await cursor.fetchall()
            
    kb = [[InlineKeyboardButton(text="➕ Добавить способ оплаты", callback_data="adm_add_pm")]]
    for m in methods: kb.append([InlineKeyboardButton(text=f"❌ Удалить: {parse_multilang_text(m[1], 'ru')}", callback_data=f"adm_del_pm_{m[0]}")])
    kb.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="adm_back_to_main")])
    await c.message.edit_text("💳 Управление оплатой", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "adm_add_pm")
async def adm_add_pm_start(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("Введите НАЗВАНИЕ кнопки оплаты:")
    await state.set_state(AdminStates.waiting_for_pm_title)

@dp.message(AdminStates.waiting_for_pm_title)
async def adm_add_pm_instruction(m: types.Message, state: FSMContext):
    await state.update_data(title=m.text.strip())
    await m.answer("Отправьте ИНСТРУКЦИЮ/РЕКВИЗИТЫ:")
    await state.set_state(AdminStates.waiting_for_pm_instruction)

@dp.message(AdminStates.waiting_for_pm_instruction)
async def adm_add_pm_finish(m: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("INSERT INTO custom_payment_methods (title, instruction) VALUES (?, ?)", (data['title'], m.text.strip()))
        await db.commit()
    await state.clear()
    
    main_menu = await get_main_menu(m.from_user.id)
    await m.answer("✅ Способ оплаты добавлен!", reply_markup=main_menu)

@dp.callback_query(F.data.startswith("adm_del_pm_"))
async def adm_del_payment(c: types.CallbackQuery):
    pm_id = int(c.data.split("_")[3])
    async with aiosqlite.connect("tariffs.db") as db:
        await db.execute("DELETE FROM custom_payment_methods WHERE id = ?", (pm_id,))
        await db.commit()
    await adm_manage_payments(c)

@dp.errors()
async def errors_handler(event: ErrorEvent):
    logging.error(f"Произошла ошибка: {event.exception}")
    tb_lines = traceback.format_exception(type(event.exception), event.exception, event.exception.__traceback__)
    tb_text = "".join(tb_lines)
    if len(tb_text) > 3500: tb_text = tb_text[-3500:]
    error_message = (
        f"⚠️ <b>КРИТИЧЕСКАЯ ОШИБКА В РАБОТЕ БОТА!</b>\n\n"
        f"🔍 <b>Тип:</b> {type(event.exception).__name__}\n"
        f"💬 <b>Описание:</b> {event.exception}\n\n"
        f"📋 <b>Стек вызовов (Traceback):</b>\n<code>{tb_text}</code>"
    )
    try: await bot.send_message(chat_id=ADMIN_ID, text=error_message, parse_mode="HTML")
    except Exception as e: print(f"Не удалось отправить уведомление об ошибке админу: {e}")
    return True

async def main():
    await init_db() # Сначала инициализируем БД асинхронно
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())