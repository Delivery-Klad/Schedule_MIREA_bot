import os
import requests
from json import dump, load
from time import sleep
from datetime import datetime

from methods import sender
from methods.logger import error_log
from methods.connect import db_connect
from methods.variables import admins_list, time_dict, api_host, day_dict, social_network

sm = "🤖"


def isAdmin(user_id):
    return True if user_id in admins_list else False


def validate_group(group):
    valid_group = group.split("-")
    if len(valid_group) < 3:
        return False
    if not valid_group[1].isnumeric() and not valid_group[2].isnumeric():
        return False
    return True


def get_teacher_icon(name):
    try:
        symbol = name.split(' ', 1)[0]
        return "👩‍🏫" if symbol[len(symbol) - 1] == "а" else "👨‍🏫"
    except IndexError:
        return ""


def get_time_icon(local_time):
    try:
        return time_dict[local_time[:2]]
    except Exception as er:
        error_log(er)
        return "🕐"


def get_week(user_id):
    try:
        week = requests.get(f"{api_host}current_week/").json()
        if social_network == "tg":
            text = f"<b>{week}</b> неделя"
        else:
            text = f"{week} неделя"
        sender.send_message(user_id, text)
    except Exception as er:
        error_log(er)


def get_users(user_id):
    if isAdmin(user_id):
        sql_request = "COPY (SELECT * FROM users) TO STDOUT WITH CSV HEADER"
        connect, cursor = db_connect()
        if connect is None or cursor is None:
            sender.send_message(user_id, f"{sm}Я потерял БД, кто найдет оставьте на охране и "
                                         f"повторите попытку позже")
            return
        with open("temp/users.csv", "w") as output_file:
            cursor.copy_expert(sql_request, output_file)
        sender.send_doc(user_id, "Пользователи", "temp/users.csv")
        os.remove("temp/users.csv")
        cursor.close()
        connect.close()
    else:
        sender.send_message(user_id, f"{sm}Я вас не понял")


def get_errors(user_id):
    try:
        if isAdmin(user_id):
            sql_request = "COPY (SELECT * FROM errors) TO STDOUT WITH CSV HEADER"
            connect, cursor = db_connect()
            if connect is None or cursor is None:
                sender.send_message(user_id, f"{sm}Я потерял БД, кто найдет оставьте на охране и "
                                             f"повторите попытку позже")
                return
            with open("temp/errors.csv", "w") as output_file:
                cursor.copy_expert(sql_request, output_file)
            sender.send_doc(user_id, "Лог ошибок", "temp/errors.csv")
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
        else:
            sender.send_message(user_id, f"{sm}Я вас не понял")
    except Exception as er:
        error_log(er)


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
            sender.send_message(user_id, f"{sm}У вас не указана группа\n"
                                         f"/group, чтобы указать группу")
            return
        except Exception as er:
            error_log(er)
    except Exception as er:
        error_log(er)
        try:
            sender.send_message(user_id, f"{sm}Не удается получить вашу группу\n"
                                         f"/group, чтобы указать группу")
        except Exception as err:
            error_log(err)
        return


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
        if i.split("\n")[0] == day_dict[day_num + 1]:
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
        sender.send_message(user_id, f"{sm}Не удается связаться с API\nПроверяю кэшированное расписание")
    if schedule.status_code == 503:
        try:
            print(f"Поиск кэшированного расписания для группы '{group}'")
            with open(f"cache/{group}.json") as file:
                lessons = load(file)
        except FileNotFoundError:
            if social_network == "tg":
                text = f"{sm}<b>Кэшированое расписание для вашей группы не найдено</b>"
            else:
                text = f"{sm}Кэшированое расписание для вашей группы не найдено"
            sender.send_message(user_id, text)
            return
    messages, message, prev_day = [], "", -1
    for i in lessons:
        try:
            if i['day_of_week'] != prev_day:
                if message != "":
                    messages.append(message)
                message = ""
                message += f"{day_dict[i['day_of_week']]}\n"
                prev_day = i['day_of_week']
            try:
                lesson_type = f" ({i['lesson_type']['short_name']})"
            except TypeError:
                lesson_type = ""
            if i['teacher'] is None:
                teacher = ""
            else:
                name = i['teacher'][0]['name']
                teacher = f"{get_teacher_icon(name)} {name}"
            if i['room'] is None:
                room = ""
            else:
                room = i['room']['name']
            if social_network == "tg":
                message += f"<b>{i['call']['call_num']} пара (<code>{room}</code>" \
                           f"{get_time_icon(i['call']['begin_time'])}" \
                           f"{i['call']['begin_time']} - {i['call']['end_time']})</b>\n" \
                           f"{i['discipline']['name']}{lesson_type}\n" \
                           f"{teacher}\n\n"
            else:
                message += f"{i['call']['call_num']} пара ({room}" \
                           f"{get_time_icon(i['call']['begin_time'])}" \
                           f"{i['call']['begin_time']} - {i['call']['end_time']})\n" \
                           f"{i['discipline']['name']}{lesson_type}\n" \
                           f"{teacher}\n\n"
        except Exception as er:
            error_log(er)
    messages.append(message)
    return messages


def cache():
    print("Caching schedule...")
    week_num = requests.get(f"{api_host}current_week/").json()
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
            res = requests.get(f"{api_host}lesson/?group={i[0]}&specific_week={week_num}")
            if res.status_code != 200:
                failed += 1
                print(f"Caching failed {res} Group '{i[0]}'")
            else:
                print(f"Caching success {res} Group '{i[0]}'")
                lessons = res.json()
                with open(f"cache/{i[0]}.json", "w") as file:
                    dump(lessons, file)
                sleep(0.1)
    except Exception as er:
        error_log(er)
    if failed == len(local_groups):
        sleep(3600)
        cache()
