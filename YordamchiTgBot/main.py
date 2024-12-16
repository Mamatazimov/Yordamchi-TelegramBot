import asyncio
import sqlite3
from os import getenv

import requests


from dotenv import load_dotenv
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

load_dotenv()

token = getenv("Token")
# Dispacher va Bot
dp = Dispatcher()
bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML) )

# Malumotlar bazasini chaqirish
conn = sqlite3.connect("users_list.db", check_same_thread=False)
cursor = conn.cursor()

# Jadval yaratish
cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_lists (
        user_id INTEGER,
        item TEXT,
        reminder_text TEXT,
        reminder_time TEXT
    )
""")
conn.commit()

scheduler_sig = AsyncIOScheduler()


ex_api = getenv("ex_api")
# Valyuta kurslarini api orqali funksiyaga yuklash
def get_exchange( symbols="USD,UZS,RUB"):

    ex_url = f"https://api.exchangeratesapi.io/v1/latest?access_key={ex_api}&symbols={symbols}"

    ex_response = requests.get(url=ex_url)

    if ex_response.status_code == 200:
        data = ex_response.json()
        return data
    else:
        return {"error":f"{ex_response.status_code}"}

# Tugma uchun malumot saqlovchi
class SharedContext:
    def __init__(self):
        self.value = None

context_list = SharedContext()
context_reg = SharedContext()

class Kv_equation_class(StatesGroup):
    waiting_abc = State()


class ReminderStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_time = State()

    # builder tugmalarii


builder = InlineKeyboardBuilder()

builder.row(
    InlineKeyboardButton(text="Valyuta narxlari", callback_data='button_1'),
    InlineKeyboardButton(text="Ro'yhatlar", callback_data='button_2'),
    )
builder.row(
    InlineKeyboardButton(text="Eslatma", callback_data='button_3'),
    InlineKeyboardButton(text="Kvadrad tenglama", callback_data='button_4')
)

builder_keyboard = builder.as_markup()


# start kamanda
@dp.message(CommandStart())
async def main_menu(message: Message):
    await message.reply("Hush kelibsiz!\nMen sizga har xil yo'nalishlarda biroz yordam berish uchun yaratilganman.\nQuyidagilardan birini tanlashingiz mumkin...", reply_markup=builder_keyboard)

# Exchange
@dp.callback_query(lambda c: c.data == "button_1")
async def ex_button(callback_query: types.CallbackQuery):
    await callback_query.answer("Valyuta narxlari")
    rates = get_exchange()

    if 'error' in rates:
        await bot.send_message(callback_query.from_user.id, rates["error"])
    else:
        rates_message = "Valyuta narxlari Amerika dollariga ya'ni USD ga nisbatan o'lchanyabdi.\nHozirgi valyuta kurslari:\n"

        for currency, rate in rates["rates"].items():
            rates_message += f"{currency}: {rate}\n"
        await bot.send_message(callback_query.from_user.id, rates_message)

# Royhat button funksiya
@dp.callback_query(lambda c: c.data == "button_2")
async def royhat_keyboard(callback_query: types.CallbackQuery):
    await callback_query.answer("Ro'yhatlar bo'limi")
    roy_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Ro'yxatni ko'rish", callback_data="view_list"),
        InlineKeyboardButton(text="➕ Element qo'shish", callback_data="add_item")],
        [InlineKeyboardButton(text="🗑 Ro'yxatni tozalash", callback_data="clear_list")],
        [InlineKeyboardButton(text="Asosiy menu", callback_data="back_main_menu")]
    ])
    context_list.value = roy_keyboard
    await callback_query.message.edit_text("Quyidagilardan birini tanlang:", reply_markup=roy_keyboard)
    



# list
@dp.callback_query(lambda c: c.data in ["view_list", "add_item", "clear_list","back_main_menu"])
async def list_button(callback_query: types.CallbackQuery):

    user_id = callback_query.from_user.id
    roy_keyboard = context_list.value

    if callback_query.data == "view_list":
        cursor.execute("SELECT item FROM user_lists WHERE user_id = ? AND item IS NOT NULL", (user_id,))
        items = cursor.fetchall()
        
        if items:
            formatted_list = "\n".join([f"{i + 1}. {item[0]}" for i, item in enumerate(items)])
            await callback_query.message.edit_text(f"Sizning ro'yxatingiz:\n{formatted_list}",
                                             reply_markup=roy_keyboard)
        else:
            await callback_query.message.edit_text("Ro'yxatingiz bo'sh. Element qo'shing.", reply_markup=roy_keyboard)

    elif callback_query.data == "add_item":
        await callback_query.message.edit_text("Qo'shmoqchi bo'lgan elementni yozing:")

        @dp.message()
        async def receive_item(msg: types.Message):
            item = msg.text
            cursor.execute("INSERT INTO user_lists (user_id, item) VALUES (?,? )", (user_id, item))
            conn.commit()
            await msg.answer(f"Element qo'shildi: {item}", reply_markup=roy_keyboard)

    elif callback_query.data == "clear_list":
        cursor.execute("DELETE FROM user_lists WHERE user_id = ? AND item IS NOT NULL", (user_id,))
        conn.commit()
        await callback_query.message.edit_text("Ro'yxat tozalandi!", reply_markup=roy_keyboard)
    
    elif callback_query.data == "back_main_menu" :
        await callback_query.message.edit_text("Hush kelibsiz!\nMen sizga har xil yo'nalishlarda biroz yordam berish uchun yaratilganman.\nQuyidagilardan birini tanlashingiz mumkin...", reply_markup=builder_keyboard)



# Eslatma keyboard
@dp.callback_query(lambda c: c.data == "button_3")
async def signal_keyboard(callback_query: types.CallbackQuery):
    await callback_query.answer("Eslatma")
    sig_keyboard= InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Eslatma vaqtini belgilash", callback_data="add_signal"),
        InlineKeyboardButton(text="Barcha eslatmalarni o'chirish", callback_data="rem_signal")],
        [InlineKeyboardButton(text="Barcha eslatmalar", callback_data="all_signal")],
        [InlineKeyboardButton(text="Asosiy menu", callback_data="back_main-menu")]
    ])
    context_reg.value = sig_keyboard
    await callback_query.message.edit_text("Quyidagilardan birini tanlang:", reply_markup=sig_keyboard)
    

# 2. Eslatma jarayonini boshlash
@dp.callback_query(lambda c: c.data == "add_signal")
async def start_reminder(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Esdalik matnini kiriting:")
    await state.set_state(ReminderStates.waiting_for_text)  # Holatni boshlash



# 3. Esdalik matnini qabul qilish
@dp.message(ReminderStates.waiting_for_text)
async def get_reminder_text(message: types.Message, state: FSMContext):
    await state.update_data(reminder_text=message.text)  # Matnni saqlash
    await message.answer("Esdalik uchun vaqtni kiriting (format: YYYY-MM-DD HH:MM:SS):")
    await state.set_state(ReminderStates.waiting_for_time)  # Keyingi bosqich

# 4. Vaqtni qabul qilish va saqlash
@dp.message(ReminderStates.waiting_for_time)
async def get_reminder_time(message: types.Message, state: FSMContext):
    sig_keyboard = context_reg.value

    try:
        reminder_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M:%S")
        
        data = await state.get_data()
        reminder_text = data['reminder_text']

        cursor.execute(
            "INSERT INTO user_lists (user_id, reminder_text, reminder_time) VALUES (?, ?, ?)",
            (message.from_user.id, reminder_text, reminder_time.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

        scheduler_sig.add_job(send_reminder, DateTrigger(run_date=reminder_time), args=(message.from_user.id, reminder_time, reminder_text))
        await message.answer("Esdalik muvaffaqiyatli saqlandi!", reply_markup=sig_keyboard)
        await state.clear()


    except ValueError:
        await message.answer("Vaqt formati noto'g'ri! Iltimos, YYYY-MM-DD HH:MM:SS formatida kiritib ko'ring.", reply_markup=sig_keyboard)
# Eslatamni jo'natish
async def send_reminder(user_id,r_time,r_text):
    try:
        await bot.send_message(user_id, f"Eslatma vaqti bo'ldi:\nText :{r_text},\nVaqt :{r_time}")
    except Exception as e:
        print(f"Xatolik yuz berdi :  {e}")

# Eslatmalarni o'chirish
@dp.callback_query(lambda c: c.data == "rem_signal")
async def remove_signal(callback_query: types.CallbackQuery):
        user_id = callback_query.from_user.id 
        sig_keyboard = context_reg.value

        cursor.execute("DELETE FROM user_lists WHERE user_id = ? AND reminder_text IS NOT NULL AND reminder_time IS NOT NULL", (user_id,))
        conn.commit()
        await callback_query.message.edit_text("Ro'yxat tozalandi!", reply_markup=sig_keyboard)
    
# Barcha eslatmalar
@dp.callback_query(lambda c: c.data == "all_signal")
async def all_signal_funk(callback_query: types.CallbackQuery):
        user_id = callback_query.from_user.id
        cursor.execute("SELECT reminder_text , reminder_time FROM user_lists WHERE user_id = ? AND reminder_text IS NOT NULL AND reminder_time IS NOT NULL", (user_id,))
        items = cursor.fetchall()
        sig_keyboard = context_reg.value
        
        if items:
            lines = []

            for i, (reminder_time, reminder_text) in enumerate(items):
                
                line = f"{i + 1}. {reminder_text} : {reminder_time}"
                lines.append(line)

            formatted_list = "\n".join(lines)

            await callback_query.message.edit_text(f"Sizning ro'yxatingiz:\n{formatted_list}",
                                             reply_markup=sig_keyboard)
        else:
            await callback_query.message.edit_text("Ro'yxatingiz bo'sh. Element qo'shing.", reply_markup=sig_keyboard)
# Asosiy menuga qaytish
@dp.callback_query(lambda c: c.data == "back_main-menu")
async def main_menu_signal(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("Hush kelibsiz!\nMen sizga har xil yo'nalishlarda biroz yordam berish uchun yaratilganman.\nQuyidagilardan birini tanlashingiz mumkin...", reply_markup=builder_keyboard)

# Kv_tenglama_keyboard
kv_builder = InlineKeyboardBuilder()
kv_builder.row(
    InlineKeyboardButton(text="Yana foydalanish", callback_data="kv_again"),
    InlineKeyboardButton(text="Asosiy menu", callback_data="main-menu")
)
kv_tenglama_kybrd = kv_builder.as_markup()

# Kvadrad tenglama
@dp.callback_query(lambda c: c.data in ["button_4", "kv_again"])
async def kv_equation(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "button_4" or callback_query.data == "kv_again" :
        await callback_query.answer("Kvadrad tenglama")
        await callback_query.message.answer("Kvadrad tanglama qiymatlarini kiriting:(ax²+bx+c=0) tenglamadan abc ni (a b c) tartibida kiriting:")
        await state.set_state(Kv_equation_class.waiting_abc) # Xabarni olish



@dp.message(Kv_equation_class.waiting_abc)
async def Kv_equation_calculating(message: types.Message, state: FSMContext):
    await state.update_data(value_abc=message.text) 
    try:
        data = await state.get_data()
        value_abc = data['value_abc']
        list_value_abc = value_abc.strip(" ").split()
        value_a , value_b , value_c = map(int, list_value_abc)
        diskreminat = (value_b**2)-(4*value_c*value_a)
        diskreminat_ildiz_osti = diskreminat**(1/2)
        if diskreminat_ildiz_osti > 0:
            x_1 = (-value_b-diskreminat_ildiz_osti)/(2*value_a)
            x_2 = (-value_b+diskreminat_ildiz_osti)/(2*value_a)
            await message.answer(f"Tenglamani yechimlari: {x_1} , {x_2}", reply_markup=kv_tenglama_kybrd)
        elif diskreminat_ildiz_osti == 0:
            x = -value_b/(2*value_a)
            await message.answer(f"Tenglama bitta yechimga ega bo'ldi:{x}", reply_markup=kv_tenglama_kybrd)
        elif diskreminat_ildiz_osti < 0:
            await message.answer("Tenglama yechimga ega emas", reply_markup=kv_tenglama_kybrd)
    except ValueError:
        await message.answer("Noto'gri qiymat kiritdingiz.Iltimos to'g'ri qiymat kiriting.\nEslatma: Agar (a) qiymatingiz yo'q bo'lsa uni 1,(b) qiymatingiz yo'q bo'lsa 1 yoki (c) qiymatingiz yo'q bo'lsa uni 0 deb belgilang!!!\nDasturchi:'Ushbu xatoliklarni to\'g\'irlashim mumkin edi, lekin erindim:)'", reply_markup=kv_tenglama_kybrd)
    except TypeError:
        await message.answer("Uzur lekin bot cheksiz kasr yoki ildiz ostilik javoblarni chiqara olmaydi", reply_markup=kv_tenglama_kybrd)



@dp.callback_query(lambda c: c.data == "main-menu")
async def kv_to_main_menu(callback_query: types.CallbackQuery):
        await callback_query.message.edit_text("Hush kelibsiz!\nMen sizga har xil yo'nalishlarda biroz yordam berish uchun yaratilganman.\nQuyidagilardan birini tanlashingiz mumkin...", reply_markup=builder_keyboard)


async def on_startup():
    scheduler_sig.start()


# Asosiy ishga tushirish funksiyasi
async def main():
    try:
        await on_startup()
        await dp.start_polling(bot)
    finally:
        conn.close()
        await bot.session.close()




    

if __name__ == "__main__":
    asyncio.run(main())


