import logging
import os
import time
from http import HTTPStatus

import requests
import simplejson
import telegram
from dotenv import load_dotenv

from exceptions import TokenError

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger.addHandler(logging.StreamHandler())

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
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError as error:
        logger.error('Ошибка при отправке сообщения')
        raise error


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException as error:
        logger.error('При запросе возникла ошибка')
        raise error

    status_code = homework_statuses.status_code

    if status_code == HTTPStatus.OK:
        try:
            return homework_statuses.json()
        except simplejson.errors.JSONDecodeError as error:
            logger.error('Ошибка при преобразовании ответа в JSON')
            raise error
    else:
        logger.error(f'Запрос не удался: код ошибки {status_code}')
        raise requests.exceptions.RequestException(
            f'Запрос не удался: код ошибки {status_code}'
        )


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        logger.error('Ответ API некорректен: ответ API не является словарем')
        raise TypeError(
            'Ответ API некорректен: ответ API не является словарем'
        )

    if 'current_date' not in response or 'homeworks' not in response:
        logger.error(
            'Ответ API некорректен: «current_date» и «homeworks»'
            'не найдены в наборе существующих ключей'
        )
        raise KeyError(
            'Ответ API некорректен: «current_date» и «homeworks»'
            'не найдены в наборе существующих ключей'
        )

    if not isinstance(response.get('homeworks'), list):
        logger.error(
            'Ответ API некорректен: по ключу «homeworks»'
        )
        raise TypeError(
            'Ответ API некорректен: по ключу «homeworks»'
        )
    else:
        logger.debug('ответ API корректный')
        return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        logger.error(f'Такой домашней работы нет в системе {homework}')
        raise KeyError('Такой домашней работы нет в системе')
    homework_name = homework.get('homework_name')

    if homework.get('status') not in HOMEWORK_STATUSES:
        logger.error('Такого статуса не существует')
        raise KeyError('Такого статуса не существует')

    verdict = HOMEWORK_STATUSES[homework.get('status')]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        return True
    else:
        return False


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_text = 'Отсутствует обязательная переменная окружения'
        logging.critical(error_text)
        raise TokenError(error_text)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    sent_message = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != sent_message:
                    send_message(bot, message)
                    logger.info('Сообщение успешно отправлено')
                    sent_message = message
                else:
                    logger.info(
                        'Работа пока не проверена: статус не обновлялся'
                    )
            else:
                message = 'В указанные даты домашних заданий не найдено'
                if message != sent_message:
                    send_message(bot, message)
                    logger.info('В указанные даты домашних заданий не найдено')
                    sent_message = message
                else:
                    logger.info('В указанные даты все еще нет сданных работ')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
