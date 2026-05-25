#!/usr/bin/env python3
"""
Telegram бот для відстеження акцій у магазинах
Магазини: Сільпо, АТБ, Новус та інші
"""

import logging
import json
import os
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)

# ─── Налаштування ───────────────────────────────────────────────────────────
TOKEN = "8846252745:AAG31dgh_fRLS1JPM2pTY7_TaqYDPm9Fipg"  # Замінити на свій токен
DATA_FILE = "sales.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Стани для ConversationHandler
(CHOOSE_STORE, ENTER_PRODUCT, ENTER_PRICE, ENTER_OLD_PRICE,
 ENTER_DISCOUNT, ENTER_DATE, CONFIRM) = range(7)

STORES = ["Сільпо", "АТБ", "Новус", "Ашан", "Метро", "Інший"]
STORE_EMOJI = {
    "Сільпо": "🟡",
    "АТБ": "🔴",
    "Новус": "🟢",
    "Ашан": "🔵",
    "Метро": "🟠",
    "Інший": "⚪️",
}


# ─── Робота з даними ─────────────────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sales": []}


def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_active_sales() -> list:
    data = load_data()
    today = date.today().isoformat()
    active = []
    for sale in data["sales"]:
        end = sale.get("end_date", "9999-12-31")
        if end >= today:
            active.append(sale)
    return active


def get_sales_by_store(store: str) -> list:
    return [s for s in get_active_sales() if s["store"] == store]


def add_sale(sale: dict):
    data = load_data()
    sale["id"] = len(data["sales"]) + 1
    sale["added"] = datetime.now().isoformat()
    data["sales"].append(sale)
    save_data(data)


def delete_sale(sale_id: int):
    data = load_data()
    data["sales"] = [s for s in data["sales"] if s.get("id") != sale_id]
    save_data(data)


# ─── Клавіатури ──────────────────────────────────────────────────────────────
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Додати акцію", callback_data="add_sale")],
        [InlineKeyboardButton("📋 Всі акції", callback_data="all_sales"),
         InlineKeyboardButton("🏪 По магазину", callback_data="by_store")],
        [InlineKeyboardButton("💰 Найкращі знижки", callback_data="best_deals")],
        [InlineKeyboardButton("🗑 Видалити акцію", callback_data="delete_sale")],
    ])


def store_keyboard(callback_prefix="store_"):
    buttons = []
    row = []
    for i, store in enumerate(STORES):
        emoji = STORE_EMOJI.get(store, "⚪️")
        row.append(InlineKeyboardButton(f"{emoji} {store}", callback_data=f"{callback_prefix}{store}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Скасувати", callback_data="cancel")]])


# ─── Форматування ────────────────────────────────────────────────────────────
def format_sale(sale: dict) -> str:
    store = sale.get("store", "?")
    emoji = STORE_EMOJI.get(store, "⚪️")
    product = sale.get("product", "?")
    price = sale.get("price", "?")
    old_price = sale.get("old_price")
    discount = sale.get("discount")
    end_date = sale.get("end_date", "не вказано")

    text = f"{emoji} *{store}* — {product}\n"
    text += f"   💵 Ціна: *{price} грн*"

    if old_price:
        text += f" ~~{old_price} грн~~"
    if discount:
        text += f" 🏷 -{discount}%"
    text += f"\n   📅 До: {end_date}\n"
    return text


# ─── Хендлери команд ─────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Привіт! Я бот для відстеження акцій* 🛒\n\n"
        "Допоможу тобі зібрати всі акції з улюблених магазинів "
        "в одному місці та знайти найкращі пропозиції!\n\n"
        "Обери дію:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Як користуватись ботом:*\n\n"
        "➕ *Додати акцію* — збережи нову акцію з магазину\n"
        "📋 *Всі акції* — перегляд усіх активних акцій\n"
        "🏪 *По магазину* — акції конкретного магазину\n"
        "💰 *Найкращі знижки* — топ-10 акцій за розміром знижки\n"
        "🗑 *Видалити* — прибрати застарілу акцію\n\n"
        "Команди:\n"
        "/start — головне меню\n"
        "/add — додати акцію\n"
        "/list — всі акції\n"
        "/best — найкращі знижки"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── Перегляд акцій ──────────────────────────────────────────────────────────
async def show_all_sales(query, context):
    sales = get_active_sales()
    if not sales:
        await query.edit_message_text(
            "📭 Акцій поки немає. Додай першу!",
            reply_markup=main_menu_keyboard()
        )
        return

    # Групуємо по магазинах
    by_store = {}
    for sale in sales:
        store = sale.get("store", "Інший")
        by_store.setdefault(store, []).append(sale)

    text = f"📋 *Всі активні акції ({len(sales)}):*\n\n"
    for store, store_sales in by_store.items():
        text += f"{'─' * 20}\n"
        for sale in store_sales:
            text += format_sale(sale)
        text += "\n"

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
        ]])
    )


async def show_best_deals(query, context):
    sales = get_active_sales()
    # Фільтруємо ті, що мають знижку
    with_discount = [s for s in sales if s.get("discount")]
    with_discount.sort(key=lambda x: int(x.get("discount", 0)), reverse=True)
    top = with_discount[:10]

    if not top:
        await query.edit_message_text(
            "😔 Немає акцій зі знижками. Додай акції з відсотком знижки!",
            reply_markup=main_menu_keyboard()
        )
        return

    text = "💰 *Топ знижки:*\n\n"
    for i, sale in enumerate(top, 1):
        text += f"{i}. {format_sale(sale)}"

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
        ]])
    )


async def show_store_sales(query, store_name):
    sales = get_sales_by_store(store_name)
    emoji = STORE_EMOJI.get(store_name, "⚪️")

    if not sales:
        await query.edit_message_text(
            f"{emoji} *{store_name}*\n\nАкцій немає. Додай першу!",
            parse_mode="Markdown",
            reply_markup=store_keyboard("store_")
        )
        return

    text = f"{emoji} *{store_name}* — акції ({len(sales)}):\n\n"
    for sale in sales:
        text += format_sale(sale)

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 До магазинів", callback_data="by_store")
        ]])
    )


# ─── Додавання акції (ConversationHandler) ───────────────────────────────────
async def add_sale_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок діалогу додавання акції"""
    context.user_data["new_sale"] = {}
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🏪 *Оберіть магазин:*",
            parse_mode="Markdown",
            reply_markup=store_keyboard("newstore_")
        )
    else:
        await update.message.reply_text(
            "🏪 *Оберіть магазин:*",
            parse_mode="Markdown",
            reply_markup=store_keyboard("newstore_")
        )
    return CHOOSE_STORE


async def add_sale_store_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    store = query.data.replace("newstore_", "")
    context.user_data["new_sale"]["store"] = store
    await query.edit_message_text(
        f"✅ Магазин: *{store}*\n\n📦 Введіть назву товару або акції:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )
    return ENTER_PRODUCT


async def add_sale_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_sale"]["product"] = update.message.text
    await update.message.reply_text(
        "💵 Введіть акційну ціну (тільки число, наприклад: 45.90):",
        reply_markup=cancel_keyboard()
    )
    return ENTER_PRICE


async def add_sale_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.replace(",", "."))
        context.user_data["new_sale"]["price"] = price
    except ValueError:
        await update.message.reply_text("❌ Введіть правильну ціну (наприклад: 45.90)")
        return ENTER_PRICE

    await update.message.reply_text(
        "💸 Введіть стару ціну (або напишіть *пропустити*):",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )
    return ENTER_OLD_PRICE


async def add_sale_old_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text != "пропустити":
        try:
            old_price = float(text.replace(",", "."))
            context.user_data["new_sale"]["old_price"] = old_price
            # Автоматично рахуємо знижку
            price = context.user_data["new_sale"]["price"]
            discount = round((1 - price / old_price) * 100)
            context.user_data["new_sale"]["discount"] = discount
        except ValueError:
            await update.message.reply_text("❌ Введіть правильну ціну або напишіть 'пропустити'")
            return ENTER_OLD_PRICE

    await update.message.reply_text(
        "📅 Введіть дату закінчення акції у форматі *ДД.ММ.РРРР*\n"
        "або напишіть *пропустити*:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )
    return ENTER_DATE


async def add_sale_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text != "пропустити":
        try:
            d = datetime.strptime(update.message.text, "%d.%m.%Y")
            context.user_data["new_sale"]["end_date"] = d.date().isoformat()
        except ValueError:
            await update.message.reply_text(
                "❌ Невірний формат. Введіть дату як *ДД.ММ.РРРР* або *пропустити*",
                parse_mode="Markdown"
            )
            return ENTER_DATE

    # Показуємо підтвердження
    sale = context.user_data["new_sale"]
    text = "✅ *Підтвердіть акцію:*\n\n" + format_sale(sale)
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Зберегти", callback_data="confirm_save"),
             InlineKeyboardButton("❌ Скасувати", callback_data="cancel")]
        ])
    )
    return CONFIRM


async def add_sale_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_save":
        add_sale(context.user_data["new_sale"])
        await query.edit_message_text(
            "🎉 *Акцію збережено!*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await query.edit_message_text(
            "❌ Скасовано.",
            reply_markup=main_menu_keyboard()
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "❌ Скасовано.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


# ─── Видалення акції ─────────────────────────────────────────────────────────
async def show_delete_menu(query, context):
    sales = get_active_sales()
    if not sales:
        await query.edit_message_text(
            "📭 Немає акцій для видалення.",
            reply_markup=main_menu_keyboard()
        )
        return

    buttons = []
    for sale in sales[-10:]:  # Показуємо останні 10
        emoji = STORE_EMOJI.get(sale.get("store", ""), "⚪️")
        label = f"{emoji} {sale.get('store')} — {sale.get('product', '?')[:20]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"del_{sale['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])

    await query.edit_message_text(
        "🗑 *Оберіть акцію для видалення:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ─── Головний callback handler ───────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "main_menu":
        await query.edit_message_text(
            "🛒 *Головне меню:*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    elif data == "all_sales":
        await show_all_sales(query, context)
    elif data == "by_store":
        await query.edit_message_text(
            "🏪 *Оберіть магазин:*",
            parse_mode="Markdown",
            reply_markup=store_keyboard("store_")
        )
    elif data.startswith("store_"):
        store = data.replace("store_", "")
        await show_store_sales(query, store)
    elif data == "best_deals":
        await show_best_deals(query, context)
    elif data == "delete_sale":
        await show_delete_menu(query, context)
    elif data.startswith("del_"):
        sale_id = int(data.replace("del_", ""))
        delete_sale(sale_id)
        await query.edit_message_text(
            "✅ Акцію видалено!",
            reply_markup=main_menu_keyboard()
        )


# ─── Запуск бота ─────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TOKEN).build()

    # ConversationHandler для додавання акцій
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_sale_start),
            CallbackQueryHandler(add_sale_start, pattern="^add_sale$"),
        ],
        states={
            CHOOSE_STORE: [CallbackQueryHandler(add_sale_store_chosen, pattern="^newstore_")],
            ENTER_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sale_product)],
            ENTER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sale_price)],
            ENTER_OLD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sale_old_price)],
            ENTER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sale_date)],
            CONFIRM: [CallbackQueryHandler(add_sale_confirm, pattern="^(confirm_save|cancel)$")],
        },
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^cancel$")],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", lambda u, c: show_all_sales(u, c)))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Бот запущено! Натисни Ctrl+C для зупинки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
