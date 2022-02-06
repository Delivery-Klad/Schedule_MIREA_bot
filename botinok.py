import telebot
import requests
import os
import json
import time
import schedule as schedule_lib
from threading import Thread
from datetime import datetime

from methods.logger import error_log
from methods import check_env, find_classroom, variables, funcs
from methods.connect import db_connect, create_tables


api_host = "https://schedule-rtu.rtuitlab.dev/api/"
check_env.validator()
bot = telebot.TeleBot(str(os.environ.get('TOKEN')))
sm = "🤖"
group_list = []
commands = ["сегодня", "завтра", "на неделю"]
day_dict = {1: "Понедельник",
            2: "Вторник",
            3: "Среда",
            4: "Четверг",
            5: "Пятница",
            6: "Суббота"}
time_dict = {"9:": "🕘", "10": "🕦", "12": "🕐", "14": "🕝", "16": "🕟", "18": "🕕", "19": "🕢", "20": "🕘"}
delimiter = "------------------------------------------------"
time_difference = 3
response = ""
social_network = "tg"
print(bot.get_me())


@bot.message_handler(commands=['users'])
def handler_db(message):
    sql_request = "COPY (SELECT * FROM users) TO STDOUT WITH CSV HEADER"
    if funcs.isAdmin(message.from_user.id):
        connect, cursor = db_connect()
        if connect is None or cursor is None:
            bot.send_message(message.from_user.id, f"{sm}Я потерял БД, кто найдет оставьте на охране и повторите "
                                                   f"попытку позже")
            return
        with open("temp/users.csv", "w") as output_file:
            cursor.copy_expert(sql_request, output_file)
        with open("temp/users.csv", "rb") as doc:
            bot.send_document(chat_id=message.from_user.id, data=doc)
        os.remove("temp/users.csv")
        connect.commit()
        cursor.close()
        connect.close()


@bot.message_handler(commands=['errors'])
def handler_errors(message):
    try:
        sql_request = "COPY (SELECT * FROM errors) TO STDOUT WITH CSV HEADER"
        if funcs.isAdmin(message.from_user.id):
            connect, cursor = db_connect()
            if connect is None or cursor is None:
                bot.send_message(message.from_user.id, f"{sm}Я потерял БД, кто найдет оставьте на охране и повторите "
                                                       f"попытку позже")
                return
            with open("temp/errors.csv", "w") as output_file:
                cursor.copy_expert(sql_request, output_file)
            with open("temp/errors.csv", "rb") as doc:
                bot.send_document(chat_id=message.from_user.id, data=doc)
            os.remove("temp/errors.csv")
            cursor.execute("DELETE FROM errors")
            connect.commit()
            isolation_level = connect.isolation_level
            connect.set_isolation_level(0)
            cursor.execute("VACUUM FULL")
            connect.set_isolation_level(isolation_level)
            connect.commit()
            cursor.close()
            connect.close()
    except Exception as er:
        error_log(er)


@bot.message_handler(commands=['start'])
def handler_start(message):
    user_id = message.from_user.id if message.chat.type == "private" else message.chat.id
    print(f"{user_id} {message.from_user.username} {message.text}")
    try:
        user_markup = telebot.types.ReplyKeyboardMarkup(True, False)
        user_markup.row("сегодня", "завтра", "на неделю")
        text = f"<b>{sm}Доступные команды:\n" \
               f"/group (+группа если бот в беседе)- установить/изменить группу\n" \
               f"/today - расписание на сегодня\n" \
               f"/tomorrow - расписание на завтра\n" \
               f"/week - расписание на неделю\n" \
               f"/next_week - расписание на следующую неделю"
        if message.chat.type == "private":
            bot.send_message(message.from_user.id, text, reply_markup=user_markup, parse_mode="HTML",
                             disable_web_page_preview=True)
        else:
            bot.send_message(message.chat.id, text, parse_mode="HTML",
                             disable_web_page_preview=True)
    except Exception as er:
        error_log(er)
        try:
            bot.send_message(user_id, f"{sm}А ой, ошиб04ка")
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
            bot.send_message(message.from_user.id, f"{sm}Напишите вашу группу")
        else:
            try:
                group = message.text.split(" ", 1)[1]
                set_group(message, message.chat.id, group.upper())
            except IndexError:
                bot.send_message(message.chat.id, f"{sm}/group (группа)")
    except Exception as er:
        error_log(er)
        try:
            bot.send_message(user_id, f"{sm}А ой, ошиб04ка")
        except Exception as err:
            error_log(err)


def cache():
    print("Caching schedule...")
    failed, local_groups = 0, 0
    try:
        os.mkdir("cache")
    except FileExistsError:
        pass
    try:
        connect, cursor = db_connect()
        if connect is None or cursor is None:
            return
        cursor.execute("SELECT DISTINCT grp FROM users")
        local_groups = cursor.fetchall()
        for i in local_groups:
            res = requests.get(f"https://schedule-rtu.rtuitlab.dev/api/schedule/{i[0]}/week")
            if res.status_code != 200:
                failed += 1
                print(f"Caching failed {res} Group '{i[0]}'")
            else:
                print(f"Caching success {res} Group '{i[0]}'")
                lessons = res.json()
                with open(f"cache/{i[0]}.json", "w") as file:
                    json.dump(lessons, file)
                time.sleep(0.1)
    except Exception as er:
        error_log(er)
    if failed == len(local_groups):
        time.sleep(3600)
        cache()


def set_group(message, user_id, group):
    try:
        connect, cursor = db_connect()
        if connect is None or cursor is None:
            bot.send_message(user_id, f"{sm}Я потерял БД, кто найдет оставьте на охране и повторите попытку позже")
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
        bot.send_message(user_id, f"{sm}Я вас запомнил")
        try:
            group_list.pop(group_list.index(user_id))
        except Exception as er:
            if "is not in list" not in str(er):
                error_log(er)
    except Exception as er:
        error_log(er)
        bot.send_message(user_id, f"{sm}А ой, ошиб04ка")


@bot.message_handler(commands=['which_week'])
def get_week(message):
    try:
        week = requests.get(f"{api_host}current_week/").json()
        bot.send_message(message.chat.id, f"<b>{week}</b> неделя", parse_mode="HTML")
    except Exception as er:
        error_log(er)


def get_schedule(user_id, day, group, title):
    day_num = datetime.today().weekday()
    week = "week"
    if day == "tomorrow":
        day_num += 1
        if day_num > 6:
            day_num = 0
            week = "next_week"
    if day_num == 6:
        return ""
    temp = []
    for i in get_week_schedule(user_id, week, group):
        if i.split("\n")[0] == variables.day_dict[day_num + 1]:
            temp = i.split("\n")
            temp.pop(0)
    return title + "\n".join(temp)


def get_week_schedule(user_id, week, group):
    week_num = requests.get(f"{api_host}current_week/").json()
    if week == "next_week":
        week_num = 2 if week_num == 1 else 1
    schedule = requests.get(f"{api_host}lesson/?group={group}&specific_week={week_num}")
    try:
        lessons = schedule.json()
    except Exception as er:
        error_log(er)
        text = "Не удается связаться с API\nПроверяю кэшированное расписание"
        bot.send_message(user_id, f"{sm}{text}")
    if schedule.status_code == 503:
        try:
            print(f"Поиск кэшированного расписания для группы '{group}'")
            with open(f"cache/{group}.json") as file:
                lessons = json.load(file)
        except FileNotFoundError:
            bot.send_message(user_id, f"{sm}<b>Кэшированое расписание для вашей группы не найдено</b>")
            return
    messages, message, prev_day = [], "", -1
    for i in lessons:
        try:
            if i['day_of_week'] != prev_day:
                if message != "":
                    messages.append(message)
                message = ""
                message += f"{variables.day_dict[i['day_of_week']]}\n"
                prev_day = i['day_of_week']
            try:
                lesson_type = f" ({i['lesson_type']['short_name']})"
            except TypeError:
                lesson_type = ""
            if i['teacher'] is None:
                teacher = ""
            else:
                name = i['teacher'][0]['name']
                teacher = f"{funcs.get_teacher_icon(name)} {name}"
            if i['room'] is None:
                room = ""
            else:
                room = i['room']['name']
            message += f"<b>{i['call']['call_num']} пара (<code>{room}</code>" \
                       f"{funcs.get_time_icon(i['call']['begin_time'])}" \
                       f"{i['call']['begin_time']} - {i['call']['end_time']})</b>\n" \
                       f"{i['discipline']['name']}{lesson_type}\n" \
                       f"{teacher}\n\n"
        except Exception as er:
            error_log(er)
    messages.append(message)
    return messages


def get_group(user_id):
    try:
        connect, cursor = db_connect()
        cursor.execute(f"SELECT grp FROM users WHERE ids={user_id}")
        try:
            group = cursor.fetchone()[0]
            cursor.close()
            connect.close()
            return group
        except TypeError:
            bot.send_message(user_id, f"{sm}У вас не указана группа\n/group, чтобы указать группу")
            return
        except Exception as er:
            error_log(er)
    except Exception as er:
        error_log(er)
        try:
            bot.send_message(user_id, f"{sm}Не удается получить вашу группу\n/group, чтобы указать группу")
        except Exception as err:
            error_log(err)
        return


@bot.message_handler(content_types=['text'])
def handler_text(message):
    print(f"{message.from_user.id} {message.from_user.username} {message.text}")
    group = ""
    try:
        if message.from_user.id in group_list:
            if "/" in message.text or message.text in commands:
                bot.send_message(message.from_user.id, f"{sm}НАПИШИТЕ ВАШУ ГРУППУ")
                return
            set_group(message, message.from_user.id, message.text.upper())
            return
        message_text = find_classroom.find_match(message.text)
        user_id = message.from_user.id if message.chat.type == "private" else message.chat.id
        if message_text[0] == "/" or message_text in commands:
            day = datetime.today().weekday()
            text = "/group" if message.chat.type == "private" else "/group (группа)"
            if "today" in message_text.lower() or commands[0] in message_text.lower():
                group = get_group(user_id)
                if group:
                    try:
                        group_schedule = get_schedule(user_id, "today", group, "<b>Пары сегодня:\n</b>")
                        if len(group_schedule) > 50:
                            bot.send_message(user_id, group_schedule, parse_mode="HTML")
                        else:
                            text = f"{sm}<b>Сегодня воскресенье</b>" if day == 6 else f"{sm}<b>Пар не обнаружено</b>"
                            bot.send_message(user_id, text, parse_mode="HTML")
                    except Exception as er:
                        bot.send_message(user_id, f"{sm}<b>Ooops, ошибо4ка, попробуйте позже</b>", parse_mode="HTML")
                        error_log(er)
            elif "tomorrow" in message_text.lower() or commands[1] in message_text.lower():
                group = get_group(user_id)
                if group:
                    try:
                        group_schedule = get_schedule(user_id, "tomorrow", group, "<b>Пары завтра:\n</b>")
                        if len(group_schedule) > 50:
                            bot.send_message(user_id, group_schedule, parse_mode="HTML")
                        else:
                            text = f"{sm}<b>Завтра воскресенье</b>" if day == 5 else f"{sm}<b>Пар не обнаружено</b>"
                            bot.send_message(user_id, text, parse_mode="HTML")
                    except Exception as er:
                        bot.send_message(user_id, f"{sm}<b>Ooops, ошибо4ка, попробуйте позже</b>", parse_mode="HTML")
                        error_log(er)
            elif "next_week" in message_text.lower():
                group = get_group(user_id)
                if group:
                    try:
                        message = "<b>------------------------</b>\n".join(get_week_schedule(user_id,
                                                                                             "nex_week", group))
                        if len(message) > 50:
                            bot.send_message(user_id, message, parse_mode="HTML")
                        else:
                            bot.send_message(user_id, f"{sm}Пар не обнаружено", parse_mode="HTML")
                    except Exception as er:
                        bot.send_message(user_id, f"{sm}<b>Ooops, ошибо4ка</b>, попробуйте позже", parse_mode="HTML")
                        error_log(er)
            elif "week" in message_text.lower() or commands[2] in message_text.lower():
                group = get_group(user_id)
                if group:
                    try:
                        message = "<b>------------------------</b>\n".join(get_week_schedule(user_id, "week", group))
                        if len(message) > 50:
                            bot.send_message(user_id, message, parse_mode="HTML")
                        else:
                            bot.send_message(user_id, f"{sm}Пар не обнаружено", parse_mode="HTML")
                    except Exception as er:
                        bot.send_message(user_id, f"{sm}<b>Ooops, ошибо4ка</b>, попробуйте позже", parse_mode="HTML")
                        error_log(er)
        elif "week" in message_text.lower() or "неделя" in message_text.lower():
            get_week(message)
        elif len(message_text) < 8:
            text, pic = find_classroom.find_classroom(message_text)
            if text is None and pic is None:
                bot.send_message(user_id, f"{sm}Я вас не понял")
                return
            if pic is not None:
                try:
                    with open(f"maps/{pic}.png", "rb") as photo:
                        bot.send_photo(chat_id=user_id, caption=text, photo=photo)
                    return
                except FileNotFoundError:
                    bot.send_message(user_id, f"{sm}Аудитория не найдена на схемах")
                    return
            else:
                bot.send_message(user_id, f"{sm}Аудитория не найдена на схемах")
                return
        else:
            if message.chat.type == "private":
                bot.send_message(message.from_user.id, f"{sm}<b>Я вас не понял</b>", parse_mode="HTML")
    except Exception as er:
        error_log(er)


def create_thread():
    while True:
        schedule_lib.run_pending()


create_tables()
start_cache = Thread(target=cache)
start_cache.start()
schedule_lib.every().day.at("23:45").do(cache)
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
