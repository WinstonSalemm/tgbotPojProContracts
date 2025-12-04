from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from db import init_tables, save_contract
from config import API_TOKEN, API_ENDPOINT
import requests, os, json


# ==== Bot ====
bot = Bot(API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()


# ==== Кнопка SkIP ====
skip_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip")]]
)

next_item_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton("➕ Добавить товар", callback_data="add_item")],
    [InlineKeyboardButton("📄 Сформировать договор", callback_data="finish")]
])


def ok(value):   # пропуск вручную
    return "________" if value.lower() in ["-", "пропустить", "skip"] else value



# FSM ===========================
class ContractState(StatesGroup):
    buyer_name = State()
    inn = State()
    address = State()
    phone = State()
    account = State()
    bank = State()
    mfo = State()
    director = State()
    
    # товары вручную
    item_name = State()
    item_quantity = State()
    item_price = State()

    items_done = State()  # финальный этап – кнопки добавить/выполнить



# START ==========================
@router.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("📄 Начинаем создание договора.\nВведите *Имя покупателя*:", reply_markup=skip_kb)
    await state.set_state(ContractState.buyer_name)


# CLIENT DATA ====================
@router.message(ContractState.buyer_name)
async def step_name(message, state):
    await state.update_data(buyer_name=ok(message.text))
    await message.answer("Введите ИНН:", reply_markup=skip_kb)
    await state.set_state(ContractState.inn)

@router.message(ContractState.inn)
async def step_inn(message, state):
    await state.update_data(inn=ok(message.text))
    await message.answer("Юридический адрес:", reply_markup=skip_kb)
    await state.set_state(ContractState.address)

@router.message(ContractState.address)
async def step_address(message, state):
    await state.update_data(address=ok(message.text))
    await message.answer("Телефон:", reply_markup=skip_kb)
    await state.set_state(ContractState.phone)

@router.message(ContractState.phone)
async def step_phone(message, state):
    await state.update_data(phone=ok(message.text))
    await message.answer("Р/С:", reply_markup=skip_kb)
    await state.set_state(ContractState.account)

@router.message(ContractState.account)
async def step_account(message, state):
    await state.update_data(account=ok(message.text))
    await message.answer("Банк:", reply_markup=skip_kb)
    await state.set_state(ContractState.bank)

@router.message(ContractState.bank)
async def step_bank(message, state):
    await state.update_data(bank=ok(message.text))
    await message.answer("МФО:", reply_markup=skip_kb)
    await state.set_state(ContractState.mfo)

@router.message(ContractState.mfo)
async def step_mfo(message, state):
    await state.update_data(mfo=ok(message.text))
    await message.answer("Директор:", reply_markup=skip_kb)
    await state.set_state(ContractState.director)

@router.message(ContractState.director)
async def step_director(message, state):
    await state.update_data(director=ok(message.text))
    await state.update_data(items=[])   # создаём список товаров
    await message.answer("🔻 Введите название товара:")
    await state.set_state(ContractState.item_name)



# ===================== товары =====================

@router.message(ContractState.item_name)
async def item_name(message, state):
    await state.update_data(item_name=message.text)
    await message.answer(f"Введите количество `{message.text}`:")
    await state.set_state(ContractState.item_quantity)

@router.message(ContractState.item_quantity)
async def item_quantity(message, state):
    if not message.text.isdigit():
        return await message.answer("❗ Введите число")
    await state.update_data(item_quantity=int(message.text))
    await message.answer("Стоимость за 1 шт (UZS):")
    await state.set_state(ContractState.item_price)

@router.message(ContractState.item_price)
async def item_price(message, state):
    if not message.text.isdigit():
        return await message.answer("❗ Цена должна быть числом")

    data = await state.get_data()

    # добавляем товар
    item = {
        "name": data["item_name"],
        "quantity": data["item_quantity"],
        "priceNoVat": int(message.text)
    }

    items = data["items"]
    items.append(item)
    await state.update_data(items=items)

    await message.answer(
        f"Товар добавлен ✔\n\n🟦 {item['name']}\nКоличество: {item['quantity']}\nЦена: {item['priceNoVat']} сум\n",
        reply_markup=next_item_kb
    )
    await state.set_state(ContractState.items_done)



# Кнопка ➕ новый товар
@router.callback_query(F.data == "add_item")
async def add_next_item(callback, state):
    await callback.message.answer("🔻 Введите название товара:")
    await state.set_state(ContractState.item_name)
    await callback.answer()



# ===================== ФИНИШ: генерация PDF =====================

@router.callback_query(F.data == "finish")
async def generate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items = data["items"]

    payload = {
        "AgreementNumber": "AUTO",
        "BuyerName": data["buyer_name"],
        "BuyerInn": data["inn"],
        "BuyerAddress": data.get("address"),
        "BuyerPhone": data.get("phone"),
        "BuyerAccount": data.get("account"),
        "BuyerBank": data.get("bank"),
        "BuyerMfo": data.get("mfo"),
        "BuyerDirector": data.get("director"),
        "Items": items
    }

    wait = await callback.message.answer("⏳ Генерирую PDF...")

    r = requests.post(API_ENDPOINT, json=payload)
    if r.status_code != 200:
        return await wait.edit_text(f"❌ API ERROR {r.status_code}")

    filename = "contract.pdf"
    open(filename, "wb").write(r.content)

    total = sum(x["quantity"] * x["priceNoVat"] * 1.12 for x in items)
    save_contract(data['buyer_name'], data['inn'], data['phone'], total, filename)

    await wait.edit_text("✔ Договор сформирован")
    await callback.message.answer_document(FSInputFile(filename))
    await state.clear()
    await callback.answer()



# ===================== /history =====================

@router.message(F.text == "/history")
async def show_history(message: Message):
    from psycopg2 import connect
    conn = connect(
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT"),
        database=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD")
    )
    cur = conn.cursor()
    cur.execute("SELECT id, buyer_name, total_sum, file_url, created_at FROM contracts ORDER BY id DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return await message.answer("📂 История пуста")

    text = "📄 *Последние договоры:*\n\n"
    for r in rows:
        text += f"#{r[0]} – {r[1]} – {int(r[2])} сум – {r[4].strftime('%d.%m %H:%M')}\n"

    await message.answer(text)


# RUN ==========================
dp.include_router(router)

if __name__ == "__main__":
    init_tables()
    dp.run_polling(bot)
