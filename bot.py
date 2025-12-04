import json
import requests
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from config import API_TOKEN, API_ENDPOINT

bot = Bot(API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
r = Router()

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

# ---- START ----
@r.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("📄 Создание договора.\nВведите *Имя покупателя*:")
    await state.set_state(ContractState.buyer_name)

@r.message(ContractState.buyer_name)
async def step_name(message: Message, state: FSMContext):
    await state.update_data(buyer_name=message.text)
    await message.answer("ИНН покупателя:")
    await state.set_state(ContractState.inn)

@r.message(ContractState.inn)
async def step_inn(message: Message, state: FSMContext):
    await state.update_data(inn=message.text)
    await message.answer("Юр. адрес покупателя:")
    await state.set_state(ContractState.address)

@r.message(ContractState.address)
async def step_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("Контактный номер (телефон):")
    await state.set_state(ContractState.phone)

@r.message(ContractState.phone)
async def step_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Р/С + Банк:")
    await state.set_state(ContractState.account)

@r.message(ContractState.account)
async def step_account(message: Message, state: FSMContext):
    await state.update_data(account=message.text)
    await message.answer("МФО:")
    await state.set_state(ContractState.mfo)

@r.message(ContractState.mfo)
async def step_mfo(message: Message, state: FSMContext):
    await state.update_data(mfo=message.text)
    await message.answer("ФИО директора:")
    await state.set_state(ContractState.director)

@r.message(ContractState.director)
async def step_director(message: Message, state: FSMContext):
    await state.update_data(director=message.text)
    await message.answer(
        "Теперь отправь JSON товаров.\n"
        "Пример:\n\n"
        "[{\"name\":\"ОУ-5\",\"unit\":\"шт\",\"quantity\":2,\"priceNoVat\":150000}]"
    )
    await state.set_state(ContractState.items)

@r.message(ContractState.items)
async def step_items(message: Message, state: FSMContext):
    try:
        items = json.loads(message.text)     # проверка JSON
    except:
        return await message.answer("❌ Некорректный JSON. Попробуй ещё.")

    data = await state.get_data()

    payload = {
        "AgreementNumber": "AUTO",
        "BuyerName": data["buyer_name"],
        "BuyerInn": data["inn"],
        "BuyerAddress": data["address"],
        "BuyerPhone": data["phone"],
        "BuyerAccount": data["account"],
        "BuyerBank": data["bank"] if "bank" in data else "",
        "BuyerMfo": data["mfo"],
        "BuyerDirector": data["director"],
        "Items": items
    }

    msg = await message.answer("⏳ Генерирую договор...")

    r = requests.post(API_ENDPOINT, json=payload)

    if r.status_code != 200:
        return await msg.edit_text(f"⚠ Ошибка API {r.status_code}")

    file_name = "contract.pdf"
    open(file_name, "wb").write(r.content)

    await msg.edit_text("Готово. Держи договор 📄⬇")
    await message.answer_document(FSInputFile(file_name))

    await state.clear()


dp.include_router(r)

if __name__ == "__main__":
    dp.run_polling(bot)
