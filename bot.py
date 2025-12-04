from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db import init_tables, save_contract
import requests, os

from config import API_TOKEN, API_ENDPOINT

bot = Bot(API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()


def ok(v):  # пропуск — заменяем на ___
    return "________" if v.lower() in ["пропустить", "skip", "-"] else v


# FSM
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


# --- КНОПКИ ---
skip_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip")]]
)

items_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="add_item")],
        [InlineKeyboardButton(text="📄 Сформировать договор", callback_data="finish")]
    ]
)


# ────────── START ──────────
@router.message(F.text == "/start")
async def start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("📄 Начинаем создание договора\n\nВведите *имя покупателя*:", reply_markup=skip_kb)
    await state.set_state(Contract.buyer_name)


@router.callback_query(F.data == "skip")
async def skip_field(cb: CallbackQuery, state: FSMContext):
    cur = (await state.get_state()).split(":")[-1]

    await state.update_data({cur: "________"})
    await cb.answer("⏭ Пропущено")

    next_field = {
        "buyer_name": Contract.inn,
        "inn": Contract.address,
        "address": Contract.phone,
        "phone": Contract.account,
        "account": Contract.bank,
        "bank": Contract.mfo,
        "mfo": Contract.director,
        "director": Contract.item_name,
    }

    if cur != "director":
        return await cb.message.edit_text("Следующее поле:", reply_markup=skip_kb) or await state.set_state(next_field[cur])
    else:
        await cb.message.edit_text("Ввод товаров начат.\nВведите название товара:")
        await state.set_state(Contract.item_name)


# ────────── ПОЛЯ ЗАКАЗЧИКА ──────────
@router.message(Contract.buyer_name)
async def buyer(m: Message, s: FSMContext):
    await s.update_data(buyer_name=ok(m.text))
    await m.answer("ИНН:", reply_markup=skip_kb)
    await s.set_state(Contract.inn)

@router.message(Contract.inn)
async def inn(m, s):
    await s.update_data(inn=ok(m.text))
    await m.answer("Юридический адрес:", reply_markup=skip_kb)
    await s.set_state(Contract.address)

@router.message(Contract.address)
async def adr(m,s):
    await s.update_data(address=ok(m.text))
    await m.answer("Телефон:", reply_markup=skip_kb)
    await s.set_state(Contract.phone)

@router.message(Contract.phone)
async def phone(m,s):
    await s.update_data(phone=ok(m.text))
    await m.answer("Р/С:", reply_markup=skip_kb)
    await s.set_state(Contract.account)

@router.message(Contract.account)
async def acc(m,s):
    await s.update_data(account=ok(m.text))
    await m.answer("Банк:", reply_markup=skip_kb)
    await s.set_state(Contract.bank)

@router.message(Contract.bank)
async def bank(m,s):
    await s.update_data(bank=ok(m.text))
    await m.answer("МФО:", reply_markup=skip_kb)
    await s.set_state(Contract.mfo)

@router.message(Contract.mfo)
async def mfo(m,s):
    await s.update_data(mfo=ok(m.text))
    await m.answer("Директор:", reply_markup=skip_kb)
    await s.set_state(Contract.director)

@router.message(Contract.director)
async def director(m,s):
    await s.update_data(director=ok(m.text))
    await s.update_data(items=[])
    await m.answer("💼 Первый товар — введи название:")
    await s.set_state(Contract.item_name)


# ───────── ТОВАРЫ ─────────
@router.callback_query(F.data == "add_item")
async def add_new_item(cb, s):
    await cb.message.answer("Название товара:")
    await s.set_state(Contract.item_name)
    await cb.answer()


@router.message(Contract.item_name)
async def item_name(m,s):
    await s.update_data(curr_name=m.text)
    await m.answer("Количество шт:")
    await s.set_state(Contract.item_qty)


@router.message(Contract.item_qty)
async def qty(m,s):
    await s.update_data(curr_qty=int(m.text))
    await m.answer("Цена за единицу (UZS):")
    await s.set_state(Contract.item_price)


@router.message(Contract.item_price)
async def price(m,s):
    data = await s.get_data()
    item = {
        "name": data["curr_name"],
        "quantity": data["curr_qty"],
        "priceNoVat": int(m.text)
    }
    items = data.get("items", [])
    items.append(item)
    await s.update_data(items=items)

    await m.answer(
        f"📌 Добавлено: {item['name']} x{item['quantity']} по {item['priceNoVat']} сум",
        reply_markup=items_menu
    )
    await s.set_state(Contract.confirm_items)


@router.callback_query(F.data == "finish")
async def finish(cb, s):
    data = await s.get_data()
    items = data["items"]

    payload = {
        "AgreementNumber": "AUTO",
        "BuyerName": data["buyer_name"],
        "BuyerInn": data["inn"],
        "BuyerAddress": data["address"],
        "BuyerPhone": data["phone"],
        "BuyerAccount": data["account"],
        "BuyerBank": data["bank"],
        "BuyerMfo": data["mfo"],
        "BuyerDirector": data["director"],
        "Items": items,
    }

    msg = await cb.message.answer("📄 Генерация PDF...")

    r = requests.post(API_ENDPOINT, json=payload)
    if r.status_code != 200:
        return await msg.edit_text("❌ Ошибка API")

    filename = "contract.pdf"
    open(filename,"wb").write(r.content)

    save_contract(
        name=data["buyer_name"],
        inn=data["inn"],
        phone=data["phone"],
        total=sum(i["quantity"]*i["priceNoVat"]*1.12 for i in items),
        url=filename
    )

    await msg.edit_text("Готово 🔥")
    await cb.message.answer_document(FSInputFile(filename))
    await s.clear()



dp.include_router(router)

if __name__ == "__main__":
    init_tables()
    dp.run_polling(bot)
