import asyncio
import logging
from typing import Final

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import ADMIN_ID, BOT_TOKEN, SUPPORT_USERNAME
from database import (
    add_product,
    add_to_cart,
    clear_cart,
    create_order,
    delete_product,
    get_all_orders,
    get_all_products,
    get_cart,
    get_order,
    get_order_items,
    get_product,
    init_db,
    remove_from_cart,
    toggle_product_stock,
    update_order_status,
    update_track_number,
)
from keyboards import (
    admin_menu,
    cart_keyboard,
    catalog_keyboard,
    confirm_order_keyboard,
    main_menu,
    order_manage_keyboard,
    product_keyboard,
    products_manage_keyboard,
    single_product_manage_keyboard,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

CHECKOUT_ADDRESS: Final = 1
CHECKOUT_CONFIRM: Final = 2
ADD_NAME: Final = 10
ADD_DESC: Final = 11
ADD_PRICE: Final = 12
ADD_COLLECTION: Final = 13
ADD_PHOTO: Final = 14
ADD_TRACK: Final = 20

STATUS_LABELS = {
    "new": "🆕 Новый",
    "accepted": "✅ Принят",
    "shipped": "🚚 Отправлен",
    "cancelled": "❌ Отменён",
}


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID and ADMIN_ID != 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name or "друг"
    text = (
        f"Привет, {name}! 🎀\n\n"
        "Добро пожаловать в магазин SSARAFOS — брелки ручной работы.\n"
        "Выбери раздел в меню ниже."
    )
    await update.message.reply_text(text, reply_markup=main_menu())


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"По всем вопросам пиши: @{SUPPORT_USERNAME}\n"
        "Обычно отвечаем в течение нескольких часов."
    )


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Главное меню 👇", reply_markup=main_menu())


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("У тебя нет доступа к этому разделу.")
        return
    await update.message.reply_text("Панель администратора 🛠", reply_markup=admin_menu())


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    products = await get_all_products()
    if not products:
        await update.message.reply_text("Пока товаров нет, загляни позже 🌸")
        return
    await update.message.reply_text(
        "✨ Каталог SSARAFOS\n\nВыбери брелок:",
        reply_markup=catalog_keyboard(products),
    )


async def catalog_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    products = await get_all_products()
    if not products:
        await query.message.reply_text("Пока товаров нет 🌸")
        return
    await query.message.reply_text(
        "✨ Каталог SSARAFOS\n\nВыбери брелок:",
        reply_markup=catalog_keyboard(products),
    )


async def show_product_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split(":")[1])
    product = await get_product(product_id)

    if not product:
        await query.message.reply_text("Товар не найден 😔")
        return

    text = (
        f"🎀 {product['name']}\n\n"
        f"{product['description'] or 'Брелок ручной работы SSARAFOS'}\n\n"
        f"💰 Цена: {product['price']} ₽\n"
        f"📦 Коллекция: {product['collection_name'] or '—'}"
    )

    if product["photo_id"]:
        await query.message.reply_photo(
            photo=product["photo_id"],
            caption=text,
            reply_markup=product_keyboard(product_id),
        )
    else:
        await query.message.reply_text(text, reply_markup=product_keyboard(product_id))


async def cart_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Добавлено в корзину ✅")
    product_id = int(query.data.split(":")[2])
    await add_to_cart(query.from_user.id, product_id)


def format_cart(items) -> tuple[str, int]:
    lines = ["🛒 Твоя корзина:", ""]
    total = 0
    for item in items:
        subtotal = item["price"] * item["quantity"]
        total += subtotal
        lines.append(f"• {item['name']} × {item['quantity']} = {subtotal} ₽")
    lines.append("")
    lines.append(f"💰 Итого: {total} ₽")
    return "\n".join(lines), total


async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    items = await get_cart(update.effective_user.id)
    if not items:
        await update.message.reply_text("Корзина пуста 🛒\nПосмотри наш каталог 🛍")
        return
    text, _ = format_cart(items)
    await update.message.reply_text(text, reply_markup=cart_keyboard(items))


async def cart_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cart_item_id = int(query.data.split(":")[2])
    await remove_from_cart(cart_item_id)
    items = await get_cart(query.from_user.id)
    if not items:
        await query.edit_message_text("Корзина пуста 🛒")
        return
    text, _ = format_cart(items)
    await query.edit_message_text(text, reply_markup=cart_keyboard(items))


async def cart_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Корзина очищена")
    await clear_cart(query.from_user.id)
    await query.edit_message_text("Корзина очищена 🗑")


async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    items = await get_cart(query.from_user.id)
    if not items:
        await query.message.reply_text("Корзина пуста 🛒")
        return ConversationHandler.END

    await query.message.reply_text(
        "📦 Оформление заказа\n\n"
        "Напиши адрес доставки одним сообщением.\n"
        "Пример: Москва, ул. Ленина 5, кв. 10, 101000"
    )
    return CHECKOUT_ADDRESS


async def checkout_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    address = update.message.text.strip()
    if len(address) < 10:
        await update.message.reply_text("Адрес слишком короткий. Укажи полный адрес одним сообщением.")
        return CHECKOUT_ADDRESS

    items = await get_cart(update.effective_user.id)
    if not items:
        await update.message.reply_text("Корзина уже пуста 🛒")
        return ConversationHandler.END

    text, total = format_cart(items)
    context.user_data["checkout_address"] = address
    context.user_data["checkout_total"] = total

    await update.message.reply_text(
        text + f"\n📍 Адрес: {address}\n\nВсё верно?",
        reply_markup=confirm_order_keyboard(),
    )
    return CHECKOUT_CONFIRM


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    address = context.user_data.get("checkout_address")
    if not address:
        await query.message.reply_text("Адрес не найден. Оформи заказ заново.")
        return ConversationHandler.END

    items = await get_cart(query.from_user.id)
    if not items:
        await query.message.reply_text("Корзина пуста 🛒")
        return ConversationHandler.END

    _, total = format_cart(items)
    order_items = [
        {
            "product_id": item["product_id"],
            "name": item["name"],
            "price": item["price"],
            "quantity": item["quantity"],
        }
        for item in items
    ]

    order_id = await create_order(
        user_id=query.from_user.id,
        username=query.from_user.username or "",
        full_name=query.from_user.full_name or "",
        address=address,
        total=total,
        items=order_items,
    )
    await clear_cart(query.from_user.id)
    context.user_data.pop("checkout_address", None)
    context.user_data.pop("checkout_total", None)

    await query.message.reply_text(
        f"✅ Заказ #{order_id} оформлен!\n\n"
        f"📍 Адрес: {address}\n"
        f"💰 Сумма: {total} ₽\n\n"
        "Сейчас это стартер-версия: мы проверим заказ и напишем тебе по оплате/отправке. Спасибо! 🎀",
        reply_markup=main_menu(),
    )

    if is_admin(ADMIN_ID):
        admin_lines = [
            f"🛎 Новый заказ #{order_id}",
            f"👤 {query.from_user.full_name}" + (f" (@{query.from_user.username})" if query.from_user.username else ""),
            f"📍 {address}",
            f"💰 {total} ₽",
            "",
        ]
        for item in order_items:
            admin_lines.append(f"• {item['name']} × {item['quantity']} = {item['price'] * item['quantity']} ₽")
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text="\n".join(admin_lines))
        except Exception as exc:
            logger.warning("Не удалось отправить уведомление админу: %s", exc)

    return ConversationHandler.END


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("Заказ отменён")
    context.user_data.pop("checkout_address", None)
    context.user_data.pop("checkout_total", None)
    await query.message.reply_text(
        "Заказ отменён. Можешь изменить корзину и оформить снова 🛒",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"Чтобы узнать статус заказа, напиши @{SUPPORT_USERNAME} и укажи номер заказа 📦"
    )


async def admin_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return

    orders = await get_all_orders(limit=10)
    if not orders:
        await update.message.reply_text("Заказов пока нет 📭")
        return

    for order in orders:
        items = await get_order_items(order["id"])
        lines = [
            f"📦 Заказ #{order['id']}",
            f"👤 {order['full_name']}" + (f" (@{order['username']})" if order['username'] else ""),
            f"📍 {order['address']}",
            f"💰 {order['total']} ₽",
            f"📅 {order['created_at']}",
            f"Статус: {STATUS_LABELS.get(order['status'], order['status'])}",
        ]
        if order["track_number"]:
            lines.append(f"🚚 Трек-номер: {order['track_number']}")
        if items:
            lines.append("")
            for item in items:
                lines.append(f"• {item['product_name']} × {item['quantity']} = {item['price'] * item['quantity']} ₽")

        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=order_manage_keyboard(order["id"], order["status"]),
        )


async def admin_manage_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return

    products = await get_all_products(include_hidden=True)
    if not products:
        await update.message.reply_text("Товаров пока нет. Добавь через «➕ Добавить товар»." )
        return

    await update.message.reply_text(
        "Выбери товар для управления:",
        reply_markup=products_manage_keyboard(products),
    )


async def admin_product_manage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer()
        return

    await query.answer()
    product_id = int(query.data.split(":")[2])
    product = await get_product(product_id)
    if not product:
        await query.message.reply_text("Товар не найден.")
        return

    text = (
        f"🎀 {product['name']}\n"
        f"Коллекция: {product['collection_name'] or '—'}\n"
        f"Цена: {product['price']} ₽\n"
        f"Статус: {'✅ В продаже' if product['in_stock'] else '❌ Снят с продажи'}"
    )
    await query.message.reply_text(
        text,
        reply_markup=single_product_manage_keyboard(product_id, product["in_stock"]),
    )


async def admin_toggle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer()
        return

    await query.answer()
    _, _, _, product_id, new_value = query.data.split(":")
    await toggle_product_stock(int(product_id), int(new_value))
    product = await get_product(int(product_id))
    if not product:
        await query.message.reply_text("Товар не найден.")
        return
    await query.edit_message_reply_markup(
        reply_markup=single_product_manage_keyboard(product["id"], product["in_stock"])
    )


async def admin_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer()
        return

    await query.answer("Товар удалён")
    product_id = int(query.data.split(":")[2])
    await delete_product(product_id)
    await query.message.reply_text("🗑 Товар удалён.")


async def admin_back_manage_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer()
        return

    await query.answer()
    products = await get_all_products(include_hidden=True)
    if not products:
        await query.message.reply_text("Товаров пока нет.")
        return
    await query.message.reply_text(
        "Выбери товар для управления:",
        reply_markup=products_manage_keyboard(products),
    )


async def admin_order_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer()
        return

    await query.answer("Заказ принят")
    order_id = int(query.data.split(":")[2])
    await update_order_status(order_id, "accepted")
    order = await get_order(order_id)
    if order:
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=f"✅ Твой заказ #{order_id} принят в обработку! Скоро отправим 🎀",
            )
        except Exception as exc:
            logger.warning("Не удалось уведомить покупателя: %s", exc)
    await query.edit_message_reply_markup(reply_markup=order_manage_keyboard(order_id, "accepted"))


async def admin_order_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer()
        return

    await query.answer("Заказ отменён")
    order_id = int(query.data.split(":")[2])
    await update_order_status(order_id, "cancelled")
    order = await get_order(order_id)
    if order:
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=f"😔 К сожалению, заказ #{order_id} был отменён. Напиши @{SUPPORT_USERNAME} для уточнения деталей.",
            )
        except Exception as exc:
            logger.warning("Не удалось уведомить покупателя: %s", exc)
    await query.edit_message_reply_markup(reply_markup=order_manage_keyboard(order_id, "cancelled"))


async def admin_track_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer()
        return ConversationHandler.END

    await query.answer()
    order_id = int(query.data.split(":")[2])
    context.user_data["track_order_id"] = order_id
    await query.message.reply_text(f"Введи трек-номер для заказа #{order_id}:")
    return ADD_TRACK


async def admin_track_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    order_id = context.user_data.get("track_order_id")
    if not order_id:
        await update.message.reply_text("Заказ не найден. Повтори действие заново.")
        return ConversationHandler.END

    track_number = update.message.text.strip()
    await update_track_number(order_id, track_number)
    order = await get_order(order_id)
    if order:
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=(
                    f"🚚 Твой заказ #{order_id} отправлен!\n"
                    f"Трек-номер: {track_number}\n\n"
                    "Можешь отслеживать посылку на сайте службы доставки."
                ),
            )
        except Exception as exc:
            logger.warning("Не удалось уведомить покупателя: %s", exc)

    context.user_data.pop("track_order_id", None)
    await update.message.reply_text("Трек-номер сохранён ✅", reply_markup=admin_menu())
    return ConversationHandler.END


async def admin_add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text("Название брелка:")
    return ADD_NAME


async def admin_add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_product_name"] = update.message.text.strip()
    await update.message.reply_text("Описание (или отправь - чтобы пропустить):")
    return ADD_DESC


async def admin_add_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["new_product_desc"] = "" if text == "-" else text
    await update.message.reply_text("Цена в рублях (только число, например 599):")
    return ADD_PRICE


async def admin_add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.message.text.strip()
    if not value.isdigit():
        await update.message.reply_text("Нужна только цена числом. Например: 599")
        return ADD_PRICE
    context.user_data["new_product_price"] = int(value)
    await update.message.reply_text("Название коллекции (или отправь - чтобы пропустить):")
    return ADD_COLLECTION


async def admin_add_product_collection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["new_product_collection"] = "" if text == "-" else text
    await update.message.reply_text("Отправь фото брелка или напиши - чтобы пропустить:")
    return ADD_PHOTO


async def admin_add_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_id = None
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.strip() == "-":
        photo_id = None
    else:
        await update.message.reply_text("Отправь фото или символ -")
        return ADD_PHOTO

    await add_product(
        name=context.user_data["new_product_name"],
        description=context.user_data["new_product_desc"],
        price=context.user_data["new_product_price"],
        photo_id=photo_id,
        collection_name=context.user_data["new_product_collection"],
    )

    product_name = context.user_data["new_product_name"]
    for key in [
        "new_product_name",
        "new_product_desc",
        "new_product_price",
        "new_product_collection",
    ]:
        context.user_data.pop(key, None)

    await update.message.reply_text(
        f"✅ Товар «{product_name}» добавлен в каталог!",
        reply_markup=admin_menu(),
    )
    return ConversationHandler.END


async def admin_cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("track_order_id", None)
    for key in [
        "new_product_name",
        "new_product_desc",
        "new_product_price",
        "new_product_collection",
        "checkout_address",
        "checkout_total",
    ]:
        context.user_data.pop(key, None)

    message = update.message or (update.callback_query.message if update.callback_query else None)
    if update.callback_query:
        await update.callback_query.answer("Действие отменено")
    if message:
        await message.reply_text("Действие отменено.", reply_markup=main_menu())
    return ConversationHandler.END


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Ошибка при обработке апдейта: %s", context.error)


def build_application() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN пуст. Заполни файл .env")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))

    application.add_handler(MessageHandler(filters.Regex("^🛍 Каталог$"), show_catalog))
    application.add_handler(MessageHandler(filters.Regex("^🛒 Корзина$"), show_cart))
    application.add_handler(MessageHandler(filters.Regex("^📦 Мои заказы$"), my_orders))
    application.add_handler(MessageHandler(filters.Regex("^📞 Поддержка$"), support))
    application.add_handler(MessageHandler(filters.Regex("^🏠 В главное меню$"), back_to_main))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все заказы$"), admin_all_orders))
    application.add_handler(MessageHandler(filters.Regex("^📦 Управление товарами$"), admin_manage_products))

    checkout_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(checkout_start, pattern=r"^checkout$")],
        states={
            CHECKOUT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_address)],
            CHECKOUT_CONFIRM: [
                CallbackQueryHandler(confirm_order, pattern=r"^confirm_order$"),
                CallbackQueryHandler(cancel_order, pattern=r"^cancel_order$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel_conversation)],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(checkout_conversation)

    add_product_conversation = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Добавить товар$"), admin_add_product_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_name)],
            ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_desc)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_price)],
            ADD_COLLECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_collection)],
            ADD_PHOTO: [
                MessageHandler(filters.PHOTO, admin_add_product_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel_conversation)],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(add_product_conversation)

    track_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_track_start, pattern=r"^admin:order_track:\d+$")],
        states={
            ADD_TRACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_track_save)],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel_conversation)],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(track_conversation)

    application.add_handler(CallbackQueryHandler(show_product_card, pattern=r"^product:\d+$"))
    application.add_handler(CallbackQueryHandler(catalog_back, pattern=r"^catalog:back$"))
    application.add_handler(CallbackQueryHandler(cart_add, pattern=r"^cart:add:\d+$"))
    application.add_handler(CallbackQueryHandler(cart_remove, pattern=r"^cart:remove:\d+$"))
    application.add_handler(CallbackQueryHandler(cart_clear, pattern=r"^cart:clear$"))

    application.add_handler(CallbackQueryHandler(admin_product_manage, pattern=r"^admin:product_manage:\d+$"))
    application.add_handler(CallbackQueryHandler(admin_toggle_stock, pattern=r"^admin:toggle_stock:\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(admin_delete_product, pattern=r"^admin:delete_product:\d+$"))
    application.add_handler(CallbackQueryHandler(admin_back_manage_products, pattern=r"^admin:back_manage_products$"))
    application.add_handler(CallbackQueryHandler(admin_order_accept, pattern=r"^admin:order_accept:\d+$"))
    application.add_handler(CallbackQueryHandler(admin_order_cancel, pattern=r"^admin:order_cancel:\d+$"))

    application.add_error_handler(on_error)
    return application


def main() -> None:
    asyncio.run(init_db())
    app = build_application()
    logger.info("База данных инициализирована ✅")
    logger.info("Бот запущен 🚀")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
