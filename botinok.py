import os
from threading import Thread
from datetime import datetime

import telebot
import schedule as schedule_lib

from methods.logger import error_log
from methods import check_env, find_classroom, variables, funcs, sender
from methods.connect import create_tables

check_env.validator()
bot = telebot.TeleBot(str(os.environ.get('TOKEN')))
sm = "🤖"
group_list = []
print(bot.get_me())


@bot.message_handler(commands=['users'])
def handler_db(message):
    funcs.get_users(message.from_user.id)


@bot.message_handler(commands=['errors'])
def handler_errors(message):
    funcs.get_errors(message.from_user.id)


@bot.message_handler(commands=['which_week'])
def get_week(message):
    funcs.get_week(message.from_user.id)


@bot.message_handler(commands=['start'])
def handler_start(message):
    user_id = message.from_user.id if message.chat.type == "private" else message.chat.id
    funcs.start(message)


@bot.message_handler(commands=['group'])
def handler_group(message):
    user_id = message.from_user.id if message.chat.type == "private" else message.chat.id
    print(f"{user_id} {message.from_user.username} {message.text}")
    try:
        if message.chat.type == "private":
            if message.from_user.id not in group_list:
                try:
                    group = message.text.split(" ", 1)[1]
                    data = funcs.create_class(message.from_user.username, message.from_user.first_name,
                                              message.from_user.last_name, group, message.from_user.id)
                    funcs.set_group(data)
                    return
                except IndexError:
                    group_list.append(message.from_user.id)
            sender.send_message(message.from_user.id, f"{sm}Напишите вашу группу")
        else:
            try:
                group = message.text.split(" ", 1)[1]
                data = funcs.create_class(message.from_user.username, message.from_user.first_name,
                                          message.from_user.last_name, group, message.from_user.id)
                funcs.set_group(data)
            except IndexError:
                sender.send_message(message.chat.id, f"{sm}/group (группа)")
    except Exception as er:
        error_log(er)
        try:
            sender.send_message(user_id, f"{sm}А ой, ошиб04ка")
        except Exception as err:
            error_log(err)


@bot.message_handler(content_types=['text'])
def handler_text(message):
    print(f"{message.from_user.id} {message.from_user.username} {message.text}")
    group = ""
    try:
        if message.from_user.id in group_list:
            if "/" in message.text or message.text in variables.commands:
                sender.send_message(message.from_user.id, f"{sm}НАПИШИТЕ ВАШУ ГРУППУ")
                return
            data = funcs.create_class(message.from_user.username, message.from_user.first_name,
                                      message.from_user.last_name, message.text, message.from_user.id)
            if funcs.set_group(data):
                group_list.pop(group_list.index(data.ids))
            return
        message_text = find_classroom.find_match(message.text)
        user_id = message.from_user.id if message.chat.type == "private" else message.chat.id
        if message_text[0] == "/" or message_text in variables.commands:
            day = datetime.today().weekday()
            text = "/group" if message.chat.type == "private" else "/group (группа)"
            if "today" in message_text.lower() or variables.commands[0] in message_text.lower():
                group = funcs.get_group(user_id)
                if group:
                    try:
                        group_schedule = funcs.get_schedule(user_id, "today", group, "<b>Пары сегодня:\n</b>")
                        if len(group_schedule) > 50:
                            sender.send_message(user_id, group_schedule)
                        else:
                            text = f"{sm}<b>Сегодня воскресенье</b>" if day == 6 else f"{sm}<b>Пар не обнаружено</b>"
                            sender.send_message(user_id, text)
                    except Exception as er:
                        sender.send_message(user_id, f"{sm}<b>Ooops, ошибо4ка, попробуйте позже</b>")
                        error_log(er)
            elif "tomorrow" in message_text.lower() or variables.commands[1] in message_text.lower():
                group = funcs.get_group(user_id)
                if group:
                    try:
                        group_schedule = funcs.get_schedule(user_id, "tomorrow", group, "<b>Пары завтра:\n</b>")
                        if len(group_schedule) > 50:
                            sender.send_message(user_id, group_schedule)
                        else:
                            text = f"{sm}<b>Завтра воскресенье</b>" if day == 5 else f"{sm}<b>Пар не обнаружено</b>"
                            sender.send_message(user_id, text)
                    except Exception as er:
                        sender.send_message(user_id, f"{sm}<b>Ooops, ошибо4ка, попробуйте позже</b>")
                        error_log(er)
            elif "next_week" in message_text.lower():
                group = funcs.get_group(user_id)
                if group:
                    try:
                        message = "<b>------------------------</b>\n".join(funcs.get_week_schedule(user_id, "next_week",
                                                                                                   group, None, None))
                        if len(message) > 50:
                            sender.send_message(user_id, message)
                        else:
                            sender.send_message(user_id, f"{sm}Пар не обнаружено")
                    except Exception as er:
                        sender.send_message(user_id, f"{sm}<b>Ooops, ошибо4ка</b>, попробуйте позже")
                        error_log(er)
            elif "week" in message_text.lower() or variables.commands[2] in message_text.lower():
                group = funcs.get_group(user_id)
                if group:
                    try:
                        message = "<b>------------------------</b>\n".join(funcs.get_week_schedule(user_id, "week",
                                                                                                   group, None, None))
                        if len(message) > 50:
                            sender.send_message(user_id, message)
                        else:
                            sender.send_message(user_id, f"{sm}Пар не обнаружено")
                    except Exception as er:
                        sender.send_message(user_id, f"{sm}<b>Ooops, ошибо4ка</b>, попробуйте позже")
                        error_log(er)
            elif "room" in message_text.lower():
                try:
                    number = message_text.split()[1]
                except IndexError:
                    sender.send_message(user_id, f"{sm}Не указан номер аудитории")
                    return
                local_schedule = funcs.get_week_schedule(user_id, "week", None, None, number)
                if not local_schedule:
                    sender.send_message(user_id, f"{sm}Пар не обнаружено")
                    return
                message = "<b>------------------------</b>\n".join(local_schedule)
                if len(message) > 50:
                    sender.send_message(user_id, message)
                else:
                    sender.send_message(user_id, f"{sm}Пар не обнаружено")
        elif "week" in message_text.lower() or "неделя" in message_text.lower():
            get_week(message)
        elif len(message_text) < 8:
            text, pic = find_classroom.find_classroom(message_text)
            if text is None and pic is None:
                sender.send_message(user_id, f"{sm}Я вас не понял")
                return
            if pic is not None:
                try:
                    sender.send_photo(user_id, text, f"maps/{pic}.png")
                    return
                except FileNotFoundError:
                    sender.send_message(user_id, f"{sm}Аудитория не найдена на схемах")
                    return
            else:
                sender.send_message(user_id, f"{sm}Аудитория не найдена на схемах")
                return
        else:
            teacher = message_text[0].upper()
            teacher += message_text[1:]
            try:
                temp = teacher.split()[1]
                teacher = teacher.split()[0] + f" {temp.upper()}"
            except IndexError:
                pass
            local_schedule = funcs.get_week_schedule(user_id, "week", None, teacher, None)
            if not local_schedule:
                sender.send_message(user_id, f"{sm}Пар не обнаружено")
                return
            message = "<b>------------------------</b>\n".join(local_schedule)
            if len(message) > 50:
                sender.send_message(user_id, message)
            else:
                sender.send_message(user_id, f"{sm}Пар не обнаружено")
    except Exception as er:
        error_log(er)


def create_thread():
    while True:
        schedule_lib.run_pending()


create_tables()
start_cache = Thread(target=funcs.cache)
start_cache.start()
schedule_lib.every().day.at("01:00").do(funcs.cache)
cache_thread = Thread(target=create_thread)
print("Расписание кэширования создано!")
cache_thread.start()
print("Бот запущен!")
try:
    while True:
        try:
            bot.polling(none_stop=True, interval=0)
        except Exception as e:
            print(e)
except Exception as e:
    print(e)
