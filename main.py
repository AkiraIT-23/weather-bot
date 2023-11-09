from decouple import config
import requests
import telebot
import psycopg2
from datetime import datetime, timedelta

api_key = config("API_KEY")
bot = telebot.TeleBot(config("TOKEN"))

conn = psycopg2.connect(database=config("DATABASE"),
                        user="postgres",
                        password=config("PASSWORD"),
                        host=config("HOST"),
                        port=config("PORT"))

# Обработчик команды /add_birthday
@bot.message_handler(commands=['add_birthday'])
def add_birthday_handler(message):
    # Парсим аргументы команды
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Неправильный формат команды. Используйте: /add_birthday [Имя] [Дата рождения]")
        return

    # Получаем имя и дату рождения из аргументов
    name = args[1]
    birthdate = args[2]

    # Получаем ID пользователя, отправившего команду
    user_id = message.from_user.id

    # Добавляем информацию о дне рождения в базу данных
    add_birthday(user_id, name, birthdate)

    bot.reply_to(message, f"Информация о дне рождения для {name} добавлена в базу данных.")


# Функция добавления информации о дне рождения в базу данных
def add_birthday(user_id, name, birthdate):
    cursor = conn.cursor()
    cursor.execute("INSERT INTO birthdays (user_id, name, birthdate) VALUES (%s, %s, %s)", (user_id, name, birthdate))
    conn.commit()
    cursor.close()


# Обработчик команды /weather
@bot.message_handler(commands=['weather'])
def weather_handler(message):
    # Парсим аргументы команды
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Неправильный формат команды. Используйте: /weather [Город]")
        return

    # Получаем город из аргументов
    city = args[1]

    # Получаем информацию о погоде
    weather_info = get_weather(city)

    # Отправляем информацию о погоде в группу
    bot.reply_to(message, weather_info)


# Функция для получения информации о погоде
def get_weather(city):
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}'

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        temp = data['main']['temp']
        desc = data['weather'][0]['description']
        weather_info = f'Текущая температура в {city}: {round(temp - 273.15)} С\nОписание: {desc}'
        return weather_info
    else:
        return 'Ошибка получения данных о погоде'


# Функция для получения прогноза погоды на следующий день
def get_weather_forecast_tomorrow(city):
    # Получаем дату на следующий день
    tomorrow_date = datetime.now() + timedelta(days=1)
    tomorrow_date_str = tomorrow_date.strftime("%Y-%m-%d")

    url = f'http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}'

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        # Ищем информацию о погоде на следующий день
        for forecast in data['list']:
            if forecast['dt_txt'].split()[0] == tomorrow_date_str:
                return forecast['weather'][0]['main'], forecast['weather'][0]['description']
    return None, None


# Функция для отправки предупреждений
def send_weather_warnings(city, chat_id):
    weather, description = get_weather_forecast_tomorrow(city)
    if weather is not None:
        if weather in ['Rain', 'Thunderstorm', 'Snow', 'Mist', 'Fog', 'Extreme']:
            message = f"Завтра в городе {city} будет {description.lower()}, возьмите зонты, будьте осторожны!"
            bot.send_message(chat_id, message)
        elif weather in ['Haze', 'Smoke', 'Squall', 'Tornado']:
            message = f"Предупреждаем: завтра в городе {city} ожидается {description.lower()}, будьте в безопасности!"
            bot.send_message(chat_id, message)


# Функция для отправки оповещения за день до дня рождения
def send_birthday_reminders():
    cursor = conn.cursor()
    today = datetime.now()
    tomorrow = today + timedelta(days=1)

    # Ищем участников, у которых завтра день рождения
    cursor.execute(
        "SELECT user_id, name FROM birthdays WHERE EXTRACT(MONTH FROM birthdate) = %s AND EXTRACT(DAY FROM birthdate) = %s",
        (tomorrow.month, tomorrow.day))

    # Указываем chat_id группы для отправки оповещений
    chat_id = config("CHAT_ID")

    for row in cursor.fetchall():
        user_id, name = row
        message = f"Завтра у {name} будет день рождения!"
        bot.send_message(chat_id, message)

    cursor.close()


@bot.message_handler(commands=['help'])
def help_handler(message):
    commands = [
        "/add_birthday [Имя] [Дата рождения] - добавить день рождения",
        "/weather [Город] - получить информацию о погоде",
        "/help - показать список доступных команд и их использование"
    ]

    help_text = "Доступные команды:\n"
    for command in commands:
        help_text += f"{command}\n"

    help_text += "\nИспользование команд:\n"
    help_text += "/add_birthday [Имя] [Дата рождения] - добавить день рождения (например, /add_birthday John 2000-01-01)\n"
    help_text += "/weather [Город] - получить информацию о погоде (например, /weather Bishkek)"

    bot.reply_to(message, help_text)


if __name__ == "__main__":
    city_to_monitor = 'Bishkek'

    chat_id = config("CHAT_ID")

    send_weather_warnings(city_to_monitor, chat_id)

    send_birthday_reminders()

    bot.polling()
