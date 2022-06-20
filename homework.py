import logging
import os
import time

import requests

import telegram

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сгенерированное сообщение пользователю."""
    bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)

    status_code = homework_statuses.status_code

    if status_code == 200:
        return homework_statuses.json()
    else:
        logging.error(f'Запрос не удался: код ошибки {status_code}')
        raise Exception(f'Запрос не удался: код ошибки {status_code}')


def check_response(response):
    """Проверяет ответ API на корректность."""
    # IsDict
    if not isinstance(response, dict):
        logging.error('Ответ API некорректен: ответ API не является словарем')
        raise TypeError(
            'Ответ API некорректен: ответ API не является словарем'
        )
    # Отсутствие ожидаемых ключей в ответе API
    if 'current_date' not in response and 'homeworks' not in response:
        logging.error(
            'Ответ API некорректен: «current_date» и «homeworks»'
            'не найдены в наборе существующих ключей'
        )
        raise KeyError(
            'Ответ API некорректен: «current_date» и «homeworks»'
            'не найдены в наборе существующих ключей'
        )
    # homeworks -> list
    if not isinstance(response.get('homeworks'), list):
        logging.error(
            'Ответ API некорректен: по ключу «homeworks»'
        )
        raise TypeError(
            'Ответ API некорректен: по ключу «homeworks»'
        )
    else:
        logging.debug('ответ API корректный')
        return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        logging.error(f'Такой домашней работы нет в системе {homework}')
        raise KeyError('Такой домашней работы нет в системе')
    homework_name = homework.get('homework_name')

    if homework.get('status') not in HOMEWORK_STATUSES:
        logging.error('Такого статуса не существует')
        raise KeyError('Такого статуса не существует')

    verdict = HOMEWORK_STATUSES[homework.get('status')]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = [
        {
            PRACTICUM_TOKEN: 'PRACTICUM_TOKEN',
            TELEGRAM_TOKEN: 'TELEGRAM_TOKEN',
            TELEGRAM_CHAT_ID: 'TELEGRAM_CHAT_ID',
        }
    ]
    if all(tokens[0]):
        return True
    else:
        return logging.critical(
            f'Отсутствует обязательная переменная окружения {tokens[0][None]}'
        )


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    get_api_answer(current_timestamp)

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
            else:
                message = 'В указанные даты домашних заданий не найдено'
            send_message(bot, message)
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            bot.send_message(TELEGRAM_CHAT_ID, message)
            time.sleep(RETRY_TIME)
        else:
            logging.critical('Отсутсвует один из элементов')
            raise KeyError('Отсутсвует один из элементов')


if __name__ == '__main__':
    main()
