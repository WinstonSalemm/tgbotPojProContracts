import os
import requests
from config import API_TOKEN, API_ENDPOINT

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from db import init_tables, save_contract


# =========================
#   BOT INIT
# =========================
bot = Bot(API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()


def ok(v: str) -> str:
    return "________" if v and v.lower() in ["пропустить", "skip", "-", " "] else v


# =========================
#   FSM
# =========================
class Contract(StatesGroup):
    # реквизиты покупателя
    buyer_name = State()
    inn = State()
    address = State()
    phone = State()
    account = State()
    bank = State()
    mfo = State()
    director = State()

    # добавление товара
    item_name = State()
    item_qty = State()
    item_price = State()

    # "меню" после добавления товаров
    confirm_items = State()

    # редактирование
    editing_item_field = State()
    editing_buyer_field = State()


# =========================
#   KEYBOARDS
# =========================
def skip_kb(field: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"skip_{field}")]]
    )


items_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё товар", callback_data="add_item")],
        [InlineKeyboardButton(text="✏ Редактировать товары", callback_data="edit_items")],
        [InlineKeyboardButton(text="👤 Изменить реквизиты покупателя", callback_data="edit_buyer")],
        [InlineKeyboardButton(text="📄 Сформировать договор", callback_data="finish")],
    ]
)


# =========================
#   START
# =========================
@router.message(F.text == "/start")
async def start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("📄 Создаём договор\nВведите имя покупателя:", reply_markup=skip_kb("buyer_name"))
    await state.set_state(Contract.buyer_name)


# =========================
#   SKIP HANDLER
# =========================
@router.callback_query(F.data.startswith("skip_"))
async def skip_field(cb: CallbackQuery, state: FSMContext):
    field = cb.data[5:]
    await state.update_data({field: "________"})
    await cb.answer("⏭ Поле пропущено")

    order = ["buyer_name", "inn", "address", "phone", "account", "bank", "mfo", "director"]
    i = order.index(field)
    next_step = order[i + 1] if i < len(order) - 1 else "items"

    if next_step == "items":
        # создаём список товаров если его ещё нет
        data = await state.get_data()
        if "items" not in data:
            await state.update_data(items=[])
        await cb.message.edit_text("🛍 Введите название товара:")
        return await state.set_state(Contract.item_name)

    titles = {
        "inn": "Введите ИНН:",
        "address": "Юридический адрес:",
        "phone": "Телефон:",
        "account": "Р/С:",
        "bank": "Банк:",
        "mfo": "МФО:",
        "director": "Директор:",
    }

    await cb.message.edit_text(titles[next_step], reply_markup=skip_kb(next_step))
    await state.set_state(getattr(Contract, next_step))


# =========================
#   CUSTOMER FIELDS
# =========================
@router.message(Contract.buyer_name)
async def buyer(msg: Message, state: FSMContext):
    await state.update_data(buyer_name=ok(msg.text))
    await msg.answer("ИНН:", reply_markup=skip_kb("inn"))
    await state.set_state(Contract.inn)


@router.message(Contract.inn)
async def inn(msg: Message, state: FSMContext):
    await state.update_data(inn=ok(msg.text))
    await msg.answer("Юр. адрес:", reply_markup=skip_kb("address"))
    await state.set_state(Contract.address)


@router.message(Contract.address)
async def adr(msg: Message, state: FSMContext):
    await state.update_data(address=ok(msg.text))
    await msg.answer("Телефон:", reply_markup=skip_kb("phone"))
    await state.set_state(Contract.phone)


@router.message(Contract.phone)
async def phone(msg: Message, state: FSMContext):
    await state.update_data(phone=ok(msg.text))
    await msg.answer("Р/С:", reply_markup=skip_kb("account"))
    await state.set_state(Contract.account)


@router.message(Contract.account)
async def acc(msg: Message, state: FSMContext):
    await state.update_data(account=ok(msg.text))
    await msg.answer("Банк:", reply_markup=skip_kb("bank"))
    await state.set_state(Contract.bank)


@router.message(Contract.bank)
async def bank(msg: Message, state: FSMContext):
    await state.update_data(bank=ok(msg.text))
    await msg.answer("МФО:", reply_markup=skip_kb("mfo"))
    await state.set_state(Contract.mfo)


@router.message(Contract.mfo)
async def mfo(msg: Message, state: FSMContext):
    await state.update_data(mfo=ok(msg.text))
    await msg.answer("Директор:", reply_markup=skip_kb("director"))
    await state.set_state(Contract.director)


@router.message(Contract.director)
async def director(msg: Message, state: FSMContext):
    # создаём items по-любому
    await state.update_data(director=ok(msg.text), items=[])
    await msg.answer("🛍 Введите название товара:")
    await state.set_state(Contract.item_name)


# =========================
#   ITEMS — ADD
# =========================
@router.callback_query(F.data == "add_item")
async def add_item(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Название товара:")
    await state.set_state(Contract.item_name)
    await cb.answer()


@router.message(Contract.item_name)
async def item_name(msg: Message, state: FSMContext):
    await state.update_data(curr_name=msg.text)
    await msg.answer("Количество (шт):")
    await state.set_state(Contract.item_qty)


@router.message(Contract.item_qty)
async def qty(msg: Message, state: FSMContext):
    try:
        qty_val = int(msg.text)
    except ValueError:
        return await msg.answer("❗ Введите целое число для количества.")
    await state.update_data(curr_qty=qty_val)
    await msg.answer("Цена за единицу (UZS):")
    await state.set_state(Contract.item_price)


@router.message(Contract.item_price)
async def price(msg: Message, state: FSMContext):
    d = await state.get_data()
    try:
        price_val = int(msg.text)
    except ValueError:
        return await msg.answer("❗ Введите целое число для цены.")

    items = d.get("items", [])

    item = dict(
        name=d["curr_name"],
        quantity=d["curr_qty"],
        priceNoVat=price_val,
    )
    items.append(item)
    await state.update_data(items=items)

    await msg.answer(
        f"➕ Добавлено: {item['name']} x{item['quantity']} по {item['priceNoVat']} сум",
        reply_markup=items_menu,
    )
    await state.set_state(Contract.confirm_items)


# =========================
#   ITEMS — EDIT UI
# =========================
@router.callback_query(F.data == "edit_items")
async def edit_items(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    items = d.get("items", [])

    if not items:
        return await cb.answer("Товаров нет для редактирования", show_alert=True)

    kb_rows = [
        [InlineKeyboardButton(text=f"✏ {i+1}. {x['name']}", callback_data=f"edit_item:{i}")]
        for i, x in enumerate(items)
    ]
    kb_rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_items")])

    await cb.message.edit_text(
        "Выберите товар для изменения:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
    )
    await cb.answer()


@router.callback_query(F.data == "back_items")
async def back_items(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("Меню работы с товарами:", reply_markup=items_menu)
    await state.set_state(Contract.confirm_items)
    await cb.answer()


@router.callback_query(F.data.startswith("edit_item:"))
async def edit_item_menu(cb: CallbackQuery, state: FSMContext):
    index = int(cb.data.split(":")[1])
    await state.update_data(edit_index=index)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏ Изменить название", callback_data="edit_name")],
            [InlineKeyboardButton(text="✏ Изменить количество", callback_data="edit_qty")],
            [InlineKeyboardButton(text="✏ Изменить цену", callback_data="edit_price")],
            [InlineKeyboardButton(text="❌ Удалить товар", callback_data="del_item")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="edit_items")],
        ]
    )
    await cb.message.edit_text("Что изменить?", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "del_item")
async def del_item(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    items = d.get("items", [])
    index = d.get("edit_index")

    if items and index is not None and 0 <= index < len(items):
        removed = items.pop(index)
        await state.update_data(items=items)
        await cb.message.answer(f"🗑 Удалено: {removed['name']}")
    else:
        await cb.message.answer("❗ Не удалось удалить товар")

    await edit_items(cb, state)


@router.callback_query(F.data.in_(["edit_name", "edit_qty", "edit_price"]))
async def ask_edit_value(cb: CallbackQuery, state: FSMContext):
    action = cb.data  # edit_name / edit_qty / edit_price
    field_map = {
        "edit_name": ("name", "новое название"),
        "edit_qty": ("quantity", "новое количество"),
        "edit_price": ("priceNoVat", "новую цену"),
    }
    field, label = field_map[action]
    await state.update_data(edit_field=field)
    await state.set_state(Contract.editing_item_field)
    await cb.message.answer(f"Введите {label}:")
    await cb.answer()


@router.message(Contract.editing_item_field)
async def apply_item_edit(msg: Message, state: FSMContext):
    d = await state.get_data()
    items = d.get("items", [])
    index = d.get("edit_index")
    field = d.get("edit_field")

    if items is None or index is None or field is None or not (0 <= index < len(items)):
        await msg.answer("❗ Ошибка редактирования товара")
        return await state.set_state(Contract.confirm_items)

    new_value = msg.text

    if field in ["quantity", "priceNoVat"]:
        try:
            new_value = int(new_value)
        except ValueError:
            return await msg.answer("❗ Введите целое число.")

    items[index][field] = new_value
    await state.update_data(items=items)

    await msg.answer("✅ Товар обновлён.", reply_markup=items_menu)
    await state.set_state(Contract.confirm_items)


# =========================
#   BUYER EDIT
# =========================
@router.callback_query(F.data == "edit_buyer")
async def edit_buyer(cb: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Имя", callback_data="edit_buyer:buyer_name"),
                InlineKeyboardButton(text="ИНН", callback_data="edit_buyer:inn"),
            ],
            [
                InlineKeyboardButton(text="Адрес", callback_data="edit_buyer:address"),
                InlineKeyboardButton(text="Телефон", callback_data="edit_buyer:phone"),
            ],
            [
                InlineKeyboardButton(text="Р/С", callback_data="edit_buyer:account"),
                InlineKeyboardButton(text="Банк", callback_data="edit_buyer:bank"),
            ],
            [
                InlineKeyboardButton(text="МФО", callback_data="edit_buyer:mfo"),
                InlineKeyboardButton(text="Директор", callback_data="edit_buyer:director"),
            ],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back_items")],
        ]
    )
    await cb.message.edit_text("Что изменить в реквизитах покупателя?", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("edit_buyer:"))
async def choose_buyer_field(cb: CallbackQuery, state: FSMContext):
    field = cb.data.split(":", 1)[1]

    labels = {
        "buyer_name": "имя покупателя",
        "inn": "ИНН",
        "address": "юридический адрес",
        "phone": "телефон",
        "account": "р/с",
        "bank": "банк",
        "mfo": "МФО",
        "director": "директора",
    }

    await state.update_data(buyer_field_to_edit=field)
    await state.set_state(Contract.editing_buyer_field)
    await cb.message.answer(f"Введите новое значение для поля: {labels.get(field, field)}")
    await cb.answer()


@router.message(Contract.editing_buyer_field)
async def apply_buyer_edit(msg: Message, state: FSMContext):
    d = await state.get_data()
    field = d.get("buyer_field_to_edit")

    if not field:
        await msg.answer("❗ Ошибка: не выбрано поле для редактирования.")
        return await state.set_state(Contract.confirm_items)

    await state.update_data(**{field: ok(msg.text)})

    await msg.answer("✅ Реквизиты покупателя обновлены.", reply_markup=items_menu)
    await state.set_state(Contract.confirm_items)


# =========================
#   FINISH
# =========================
@router.callback_query(F.data == "finish")
async def finish(cb, state):
    d = await state.get_data()

    items = d.get("items", [])
    if not items:
        return await cb.answer("❗ Вы не добавили товары", show_alert=True)

    payload = dict(
        AgreementNumber="AUTO",
        BuyerName=d.get("buyer_name", "________"),
        BuyerInn=d.get("inn", "________"),
        BuyerAddress=d.get("address", "________"),
        BuyerPhone=d.get("phone", "________"),
        BuyerAccount=d.get("account", "________"),
        BuyerBank=d.get("bank", "________"),
        BuyerMfo=d.get("mfo", "________"),
        BuyerDirector=d.get("director", "________"),
        Items=items
    )

    msg = await cb.message.answer("📄 Генерация PDF...")

    try:
        r = requests.post(API_ENDPOINT, json=payload)

        print("===== API RESPONSE =====")
        print("STATUS:", r.status_code)
        print("TEXT:", r.text)
        print("URL:", API_ENDPOINT)
        print("========================")

        if r.status_code != 200:
            return await msg.edit_text(f"❌ Ошибка API ({r.status_code})\n\n{r.text}")

        with open("contract.pdf", "wb") as f:
            f.write(r.content)

        await msg.edit_text("🔥 Договор готов")
        await cb.message.answer_document(FSInputFile("contract.pdf"))
        await state.clear()

    except Exception as e:
        print("ERROR >>>", e)
        return await msg.edit_text(f"⚠ Ошибка запроса\n{e}")

# =========================
#   ENTRYPOINT
# =========================
dp.include_router(router)

if __name__ == "__main__":
    init_tables()
    dp.run_polling(bot)
