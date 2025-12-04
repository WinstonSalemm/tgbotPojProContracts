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


def ok(v):
    return "________" if v.lower() in ["пропустить", "skip", "-", ""] else v


# =========================
#   FSM
# =========================
class Contract(StatesGroup):
    buyer_name = State()
    inn = State()
    address = State()
    phone = State()
    account = State()
    bank = State()
    mfo = State()
    director = State()

    item_name = State()
    item_qty = State()
    item_price = State()

    confirm_items = State()


# =========================
#   KEYBOARDS
# =========================
def skip_kb(field):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"skip_{field}")]]
    )

items_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_item")],
        [InlineKeyboardButton(text="📄 Сформировать договор", callback_data="finish")]
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
#   SKIP HANDLER FIXED ✔
# =========================
@router.callback_query(F.data.startswith("skip_"))
async def skip_field(cb: CallbackQuery, state: FSMContext):
    field = cb.data[5:]
    await state.update_data({field: "________"})
    await cb.answer("⏭ Поле пропущено")

    order = ["buyer_name","inn","address","phone","account","bank","mfo","director"]
    i = order.index(field)
    next_step = order[i+1] if i < len(order)-1 else "items"

    if next_step == "items":
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
async def inn(msg, state):
    await state.update_data(inn=ok(msg.text))
    await msg.answer("Юр. адрес:", reply_markup=skip_kb("address"))
    await state.set_state(Contract.address)

@router.message(Contract.address)
async def adr(msg, state):
    await state.update_data(address=ok(msg.text))
    await msg.answer("Телефон:", reply_markup=skip_kb("phone"))
    await state.set_state(Contract.phone)

@router.message(Contract.phone)
async def phone(msg, state):
    await state.update_data(phone=ok(msg.text))
    await msg.answer("Р/С:", reply_markup=skip_kb("account"))
    await state.set_state(Contract.account)

@router.message(Contract.account)
async def acc(msg, state):
    await state.update_data(account=ok(msg.text))
    await msg.answer("Банк:", reply_markup=skip_kb("bank"))
    await state.set_state(Contract.bank)

@router.message(Contract.bank)
async def bank(msg, state):
    await state.update_data(bank=ok(msg.text))
    await msg.answer("МФО:", reply_markup=skip_kb("mfo"))
    await state.set_state(Contract.mfo)

@router.message(Contract.mfo)
async def mfo(msg, state):
    await state.update_data(mfo=ok(msg.text))
    await msg.answer("Директор:", reply_markup=skip_kb("director"))
    await state.set_state(Contract.director)

@router.message(Contract.director)
async def director(msg, state):
    await state.update_data(director=ok(msg.text), items=[])
    await msg.answer("🛍 Введите название товара:")
    await state.set_state(Contract.item_name)



# =========================
#   ITEMS
# =========================
@router.callback_query(F.data == "add_item")
async def add_item(cb, state):
    await cb.message.answer("Название товара:")
    await state.set_state(Contract.item_name)
    await cb.answer()

@router.message(Contract.item_name)
async def item_name(msg, state):
    await state.update_data(curr_name=msg.text)
    await msg.answer("Количество (шт):")
    await state.set_state(Contract.item_qty)

@router.message(Contract.item_qty)
async def qty(msg, state):
    await state.update_data(curr_qty=int(msg.text))
    await msg.answer("Цена за единицу (UZS):")
    await state.set_state(Contract.item_price)

@router.message(Contract.item_price)
async def price(msg, state):
    d = await state.get_data()
    item = dict(name=d["curr_name"], quantity=d["curr_qty"], priceNoVat=int(msg.text))

    items = d["items"]; items.append(item)
    await state.update_data(items=items)

    await msg.answer(f"➕ Добавлено: {item['name']} x{item['quantity']} по {item['priceNoVat']} сум",
                     reply_markup=items_menu)

    await state.set_state(Contract.confirm_items)



# =========================
#   FINISH
# =========================
@router.callback_query(F.data == "finish")
async def finish(cb, state):
    d = await state.get_data()
    items = d["items"]

    payload = dict(
        AgreementNumber="AUTO",
        BuyerName=d["buyer_name"],
        BuyerInn=d["inn"],
        BuyerAddress=d["address"],
        BuyerPhone=d["phone"],
        BuyerAccount=d["account"],
        BuyerBank=d["bank"],
        BuyerMfo=d["mfo"],
        BuyerDirector=d["director"],
        Items=items
    )

    msg = await cb.message.answer("📄 Генерация PDF...")
    r = requests.post(API_ENDPOINT, json=payload)

    if r.status_code != 200:
        return await msg.edit_text("❌ Ошибка API")

    with open("contract.pdf", "wb") as f:
        f.write(r.content)

    save_contract(
        name=d["buyer_name"],
        inn=d["inn"],
        phone=d["phone"],
        total=sum(i["quantity"] * i["priceNoVat"] * 1.12 for i in items),
        url="contract.pdf"
    )

    await msg.edit_text("🔥 Договор готов")
    await cb.message.answer_document(FSInputFile("contract.pdf"))
    await state.clear()



# =========================
dp.include_router(router)

if __name__ == "__main__":
    init_tables()
    dp.run_polling(bot)