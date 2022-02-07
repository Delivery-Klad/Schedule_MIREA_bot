import os
from threading import Thread
from datetime import datetime

import telebot
import schedule as schedule_lib

from methods.logger import error_log
from methods import check_env, find_classroom, variables, funcs, sender
from methods.connect import db_connect, create_tables

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
    print(f"{user_id} {message.from_user.username} {message.text}")
    try:
        text = f"<b>{sm}Доступные команды:\n" \
               f"/group (+группа если бот в беседе)- установить/изменить группу\n" \
               f"/today - расписание на сегодня\n" \
               f"/tomorrow - расписание на завтра\n" \
               f"/week - расписание на неделю\n" \
               f"/next_week - расписание на следующую неделю"
        if message.chat.type == "private":
            sender.send_message(message.from_user.id, text, keyboard=True)
        else:
            sender.send_message(message.chat.id, text)
    except Exception as er:
        error_log(er)
        try:
            sender.send_message(user_id, f"{sm}А ой, ошиб04ка")
        except Exception as err:
            error_log(err)


@bot.message_handler(commands=['group'])
def handler_group(message):
    user_id = message.from_user.id if message.chat.type == "private" else message.chat.id
    print(f"{user_id} {message.from_user.username} {message.text}")
    try:
        if message.chat.type == "private":
            if message.from_user.id not in group_list:
                try:
                    group = message.text.split(" ", 1)[1]
                    set_group(message, message.from_user.id, group.upper())
                    return
                except IndexError:
                    group_list.append(message.from_user.id)
            sender.send_message(message.from_user.id, f"{sm}Напишите вашу группу")
        else:
            try:
                group = message.text.split(" ", 1)[1]
                set_group(message, message.chat.id, group.upper())
            except IndexError:
                sender.send_message(message.chat.id, f"{sm}/group (группа)")
    except Exception as er:
        error_log(er)
        try:
            sender.send_message(user_id, f"{sm}А ой, ошиб04ка")
        except Exception as err:
            error_log(err)


def set_group(message, user_id, group):
    try:
        if funcs.validate_group(group):
            sender.send_message(user_id, f"{sm}Неверный формат группы")
            return
        connect, cursor = db_connect()
        if connect is None or cursor is None:
            sender.send_message(user_id, f"{sm}Я потерял БД, кто найдет оставьте на охране и повторите попытку позже")
            return
        cursor.execute(f"SELECT count(ids) FROM users WHERE ids={user_id}")
        res = cursor.fetchall()[0][0]
        if res == 0:
            cursor.execute(
                f"INSERT INTO users VALUES($taG${message.from_user.username}$taG$,"
                f"$taG${message.from_user.first_name}$taG$, $taG${message.from_user.last_name}$taG$, "
                f"$taG${group}$taG$, {user_id})")
        else:
            cursor.execute(f"UPDATE users SET grp=$taG${group}$taG$ WHERE ids={user_id}")
        connect.commit()
        cursor.close()
        connect.close()
        sender.send_message(user_id, f"{sm}Я вас запомнил")
        try:
            group_list.pop(group_list.index(user_id))
        except Exception as er:
            if "is not in list" not in str(er):
                error_log(er)
    except Exception as er:
        error_log(er)
        sender.send_message(user_id, f"{sm}А ой, ошиб04ка")


@bot.message_handler(content_types=['text'])
def handler_text(message):
    print(f"{message.from_user.id} {message.from_user.username} {message.text}")
    group = ""
    try:
        if message.from_user.id in group_list:
            if "/" in message.text or message.text in variables.commands:
                sender.send_message(message.from_user.id, f"{sm}НАПИШИТЕ ВАШУ ГРУППУ")
                return
            set_group(message, message.from_user.id, message.text.upper())
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
                        message = "<b>------------------------</b>\n".join(funcs.get_week_schedule(user_id,
                                                                                                   "next_week", group))
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
                        message = "<b>------------------------</b>\n".join(funcs.get_week_schedule(user_id,
                                                                                                   "week", group))
                        if len(message) > 50:
                            sender.send_message(user_id, message)
                        else:
                            sender.send_message(user_id, f"{sm}Пар не обнаружено")
                    except Exception as er:
                        sender.send_message(user_id, f"{sm}<b>Ooops, ошибо4ка</b>, попробуйте позже")
                        error_log(er)
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
            if message.chat.type == "private":
                sender.send_message(message.from_user.id, f"{sm}<b>Я вас не понял</b>")
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
