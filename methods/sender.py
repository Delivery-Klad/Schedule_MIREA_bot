import os
from time import sleep

import telebot

bot = telebot.TeleBot(str(os.environ.get('TOKEN')))


def send_photo(user_id, filename: str, text=None):
    with open(filename, "rb") as photo:
        bot.send_photo(chat_id=user_id, caption=text, photo=photo)


def send_doc(user_id, text: str, filename: str):
    with open(filename, "rb") as doc:
        bot.send_document(chat_id=user_id, caption=text, data=doc)


def send_message(user_id, text: str, keyboard=None):
    try:
        if keyboard is not None:
            user_markup = telebot.types.ReplyKeyboardMarkup(True, False)
            user_markup.row("сегодня", "завтра", "на неделю")
            bot.send_message(user_id, text, reply_markup=user_markup, parse_mode="HTML")
        else:
            bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        if "timeout" in str(e).lower():
            sleep(5)
            bot.send_message(user_id, text, parse_mode="HTML")
