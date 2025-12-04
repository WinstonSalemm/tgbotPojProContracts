from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import requests, json, os
from config import API_TOKEN, API_ENDPOINT


# ===== ENV токен обязателен =====
bot = Bot(API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()


# функция обработки пропусков
def ok(value):
    return "________" if value.lower() in ["-", "пропустить", "skip"] else value


# FSM состояния
class ContractState(StatesGroup):
    buyer_name = State()
    inn = State()
    address = State()
    phone = State()
    account = State()
    bank = State()
    mfo = State()
    director = State()
    items = State()


# ================= HANDLERS =================

@router.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("📄 Начинаем создание договора.\nВведите *Имя покупателя*: (или напишите `пропустить`)")
    await state.set_state(ContractState.buyer_name)


@router.message(ContractState.buyer_name)
async def step_name(message: Message, state: FSMContext):
    await state.update_data(buyer_name=ok(message.text))
    await message.answer("Введите ИНН:")
    await state.set_state(ContractState.inn)


@router.message(ContractState.inn)
async def step_inn(message: Message, state: FSMContext):
    await state.update_data(inn=ok(message.text))
    await message.answer("Юридический адрес:")
    await state.set_state(ContractState.address)


@router.message(ContractState.address)
async def step_address(message: Message, state: FSMContext):
    await state.update_data(address=ok(message.text))
    await message.answer("Телефон:")
    await state.set_state(ContractState.phone)


@router.message(ContractState.phone)
async def step_phone(message: Message, state: FSMContext):
    await state.update_data(phone=ok(message.text))
    await message.answer("Р/С:")
    await state.set_state(ContractState.account)


@router.message(ContractState.account)
async def step_account(message: Message, state: FSMContext):
    await state.update_data(account=ok(message.text))
    await message.answer("Банк:")
    await state.set_state(ContractState.bank)


@router.message(ContractState.bank)
async def step_bank(message: Message, state: FSMContext):
    await state.update_data(bank=ok(message.text))
    await message.answer("МФО:")
    await state.set_state(ContractState.mfo)


@router.message(ContractState.mfo)
async def step_mfo(message: Message, state: FSMContext):
    await state.update_data(mfo=ok(message.text))
    await message.answer("Директор:")
    await state.set_state(ContractState.director)


@router.message(ContractState.director)
async def step_director(message: Message, state: FSMContext):
    await state.update_data(director=ok(message.text))
    await message.answer("Отправьте JSON товаров:")
    await state.set_state(ContractState.items)


@router.message(ContractState.items)
async def step_items(message: Message, state: FSMContext):
    try:
        items = json.loads(message.text)
    except:
        return await message.answer("❌ Ошибка JSON.\nПример:\n`[{\"name\": \"ОУ-5\",\"unit\":\"шт\",\"quantity\":1,\"priceNoVat\":150000}]`")

    data = await state.get_data()

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
        "Items": items
    }

    msg = await message.answer("⏳ Генерирую PDF...")

    r = requests.post(API_ENDPOINT, json=payload)

    if r.status_code != 200:
        return await msg.edit_text(f"❌ Ошибка API: {r.status_code}")

    filename = "contract.pdf"
    open(filename, "wb").write(r.content)

    await msg.edit_text("Договор готов ✔")
    await message.answer_document(FSInputFile(filename))
    await state.clear()


dp.include_router(router)


if __name__ == "__main__":
    dp.run_polling(bot)
