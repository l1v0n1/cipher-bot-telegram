import logging
import string, random, sqlite3

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import API_TOKEN
from encode import AESCipher


storage = MemoryStorage()
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)


connection = sqlite3.connect('db.db')
q = connection.cursor()


q.execute('CREATE TABLE IF NOT EXISTS users (user_id int, key text)')
connection.commit()


class code(StatesGroup):
	encode = State()
	decode = State()
	enc_key = State()
	dec_key = State()


simple_keyboard = types.InlineKeyboardMarkup(row_width=2)
simple_keyboard.add(
	types.InlineKeyboardButton(text='Закодировать', callback_data='encode'),
	types.InlineKeyboardButton(text='Расшифровать', callback_data='decode')
	)


back_keyboard = types.InlineKeyboardMarkup()
back_keyboard.add(types.InlineKeyboardButton(text='Отмена', callback_data='cancel'))


async def addtobd(chat_id):
	users = q.execute("SELECT * FROM users WHERE user_id = ?", (chat_id,)).fetchall()
	if len(users) == 0:
		q.execute("INSERT INTO users (user_id) VALUES (?)", (chat_id,))
		connection.commit()


@dp.message_handler(commands='start')
async def start(message: types.Message, state: FSMContext):
	await addtobd(message.from_user.id)
	msg = await message.answer('Привет, это бот для шифровки/расшифровки текста\nИспользуй клавиатуру ниже..', reply_markup=simple_keyboard)
	await state.update_data(mid=msg.message_id)


# encode
@dp.callback_query_handler(lambda call: call.data == 'encode')
async def encoding(call, state: FSMContext):
	await addtobd(call.message.chat.id)
	data = await state.get_data()
	m = data.get('mid')
	try:
		await bot.delete_message(message_id=m, chat_id=call.message.chat.id)
	except:
		pass
	msg = await bot.send_message(call.message.chat.id, 'Укажите ключ для шифровки:', reply_markup=back_keyboard)
	await state.update_data(mid=msg.message_id)
	await code.enc_key.set()


@dp.message_handler(state=code.enc_key)
async def encode_key(message: types.Message, state: FSMContext):
	await message.delete()
	q.execute('UPDATE users SET key = ? WHERE user_id = ?', (message.text, message.from_user.id))
	connection.commit()
	data = await state.get_data()
	msg = data.get('mid')
	await bot.edit_message_text('Теперь введите текст для шифровки:', chat_id=message.chat.id, message_id=msg, reply_markup=back_keyboard)
	await code.encode.set()


@dp.message_handler(state=code.encode)
async def encode(message: types.Message, state: FSMContext):
	await message.delete()
	data = await state.get_data()
	msg = data.get('mid')
	await bot.delete_message(message_id=msg, chat_id=message.chat.id)
	key = q.execute('SELECT key FROM users WHERE user_id = ?', (message.from_user.id,)).fetchone()[0]
	try:
		text = AESCipher(message.text, key).encrypt()
		await bot.send_message(message.chat.id, 'Полученные данные:\n\nЗашифровано: `{}`\n\nБез шифра: `{}`\n\nКлюч шифровки: `{}`'.format(text, message.text, key), reply_markup=simple_keyboard, parse_mode='Markdown')
		await state.reset_state(with_data=False)
	except:
		err = await bot.send_message(text='Возникла ошибка.', chat_id=message.chat.id, reply_markup=simple_keyboard)
		await state.update_data(mid=err.message_id)
		await state.reset_state(with_data=False)


#decode
@dp.callback_query_handler(lambda call: call.data == 'decode')
async def decoding(call, state: FSMContext):
	await addtobd(call.message.chat.id)
	data = await state.get_data()
	m = data.get('mid')
	try:
		await bot.delete_message(message_id=m, chat_id=call.message.chat.id)
	except:
		pass
	msg = await bot.send_message(text='Укажите ключ для расшифровки:', chat_id=call.message.chat.id, reply_markup=back_keyboard)
	await state.update_data(mid=msg.message_id)
	await code.dec_key.set()


@dp.message_handler(state=code.dec_key)
async def decode_key(message: types.Message, state: FSMContext):
	await message.delete()
	q.execute('UPDATE users SET key = ? WHERE user_id = ?', (message.text, message.from_user.id))
	connection.commit()
	data = await state.get_data()
	msg = data.get('mid')
	await bot.edit_message_text('Теперь введите текст для расшифровки:', chat_id=message.chat.id, message_id=msg, reply_markup=back_keyboard)
	await code.decode.set()


@dp.message_handler(state=code.decode)
async def code_decode(message: types.Message, state: FSMContext):
	await message.delete()
	data = await state.get_data()
	msg = data.get('mid')
	await bot.delete_message(message_id=msg, chat_id=message.chat.id)
	key = q.execute('SELECT key FROM users WHERE user_id = ?', (message.from_user.id,)).fetchone()[0]
	try:
		text = AESCipher(message.text, key).decrypt()
		if len(text) > 0:
			await bot.send_message(text='Полученные данные:\n\nРасшифровано: `{}`\n\nЗашифровано: `{}`\n\nКлюч шифровки: `{}`'.format(text, message.text, key), chat_id=message.chat.id, reply_markup=simple_keyboard, parse_mode='Markdown')
		else:
			erm = await bot.send_message(text='Неверный ключ.', chat_id=message.chat.id, reply_markup=simple_keyboard)
			await state.update_data(mid=erm.message_id)
		await state.reset_state(with_data=False)
	except:
		errm = await bot.send_message(text='Возникла ошибка.', chat_id=message.chat.id, reply_markup=simple_keyboard)
		await state.update_data(mid=errm.message_id)
		await state.reset_state(with_data=False)


@dp.callback_query_handler(state="*", text='cancel')
async def cancel(call, state: FSMContext):
	data = await state.get_data()
	msg = data.get('mid')
	await bot.delete_message(message_id=msg, chat_id=call.message.chat.id)
	m = await bot.send_message(text='Главное меню', chat_id=call.message.chat.id, reply_markup=simple_keyboard)
	await state.update_data(mid=m.message_id)
	await state.reset_state(with_data=False)


if __name__ == '__main__':
	executor.start_polling(dp, skip_updates=True)