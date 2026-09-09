from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🛍 Каталог"), KeyboardButton("🛒 Корзина")],
            [KeyboardButton("📦 Мои заказы"), KeyboardButton("📞 Поддержка")],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📋 Все заказы"), KeyboardButton("➕ Добавить товар")],
            [KeyboardButton("📦 Управление товарами"), KeyboardButton("🏠 В главное меню")],
        ],
        resize_keyboard=True,
    )


def catalog_keyboard(products) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"{p['name']} — {p['price']} ₽", callback_data=f"product:{p['id']}")]
        for p in products
    ]
    return InlineKeyboardMarkup(rows)


def product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛒 В корзину", callback_data=f"cart:add:{product_id}")],
            [InlineKeyboardButton("◀️ Назад к каталогу", callback_data="catalog:back")],
        ]
    )


def cart_keyboard(items) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"❌ Убрать «{item['name']}»", callback_data=f"cart:remove:{item['id']}")]
        for item in items
    ]
    rows.append([InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout")])
    rows.append([InlineKeyboardButton("🗑 Очистить корзину", callback_data="cart:clear")])
    return InlineKeyboardMarkup(rows)


def confirm_order_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_order")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_order")],
        ]
    )


def order_manage_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    rows = []
    if status == "new":
        rows.append([InlineKeyboardButton("✅ Принять заказ", callback_data=f"admin:order_accept:{order_id}")])
    if status in {"new", "accepted"}:
        rows.append([InlineKeyboardButton("🚚 Добавить трек-номер", callback_data=f"admin:order_track:{order_id}")])
    if status != "cancelled":
        rows.append([InlineKeyboardButton("❌ Отменить заказ", callback_data=f"admin:order_cancel:{order_id}")])
    return InlineKeyboardMarkup(rows)


def products_manage_keyboard(products) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        status = "✅" if p["in_stock"] else "❌"
        rows.append([
            InlineKeyboardButton(
                f"{status} {p['name']} — {p['price']} ₽",
                callback_data=f"admin:product_manage:{p['id']}",
            )
        ])
    return InlineKeyboardMarkup(rows)


def single_product_manage_keyboard(product_id: int, in_stock: int) -> InlineKeyboardMarkup:
    toggle_text = "❌ Снять с продажи" if in_stock else "✅ Вернуть в продажу"
    next_value = 0 if in_stock else 1
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(toggle_text, callback_data=f"admin:toggle_stock:{product_id}:{next_value}")],
            [InlineKeyboardButton("🗑 Удалить товар", callback_data=f"admin:delete_product:{product_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin:back_manage_products")],
        ]
    )
