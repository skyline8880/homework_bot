import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import EmptyDict, Not200Status, NotListType

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')
FROM_DATE = 1549962000

RETRY_TIME = 5
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='homework_check.log',
    level=logging.INFO)
handler = RotatingFileHandler('homework_check.log', maxBytes=50000000, backupCount=5)


def send_message(bot, message):
    return bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def get_api_answer(current_timestamp):
    """Запрос и обработка информации с сервера."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    api_answer = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if api_answer.status_code != 200:
        message = f'Произошёл сбой, при переходе по ссылке: {ENDPOINT}'
        logging.error(message)
        raise Not200Status(message)
    return api_answer.json()


def check_response(response):
    """Проверка, полученных данных."""
    if response == {}:
        message = 'Ответ API, в виде пустого словаря'
        logging.error(message)
        raise EmptyDict(message)
    if not isinstance(response['homeworks'], list):
        message = 'В результате проверки, отсутствует тип данных - список'
        logging.error(message)
        raise NotListType(message)
    if not response['homeworks']:
        return response['homeworks']
    return response['homeworks'][0]


def parse_status(homework):
    """Извлечение, необходимой нам, информации."""
    if not isinstance(homework, dict):
        message = 'Отсутсвует одно или два ключевых значения'
        logging.error(message)
        raise KeyError(message)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status == 'approved':
        verdict = HOMEWORK_STATUSES['approved']
    if homework_status == 'reviewing':
        verdict = HOMEWORK_STATUSES['reviewing']
    if homework_status == 'rejected':
        verdict = HOMEWORK_STATUSES['rejected']
    return f'Изменился статус проверки работы ' \
           f'"{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия необходимых переменных."""
    if not globals().get('PRACTICUM_TOKEN') \
            or not globals().get('TELEGRAM_TOKEN') \
            or not globals().get('TELEGRAM_CHAT_ID'):
        logging.critical('Отсутствуют, необходимые переменные')
        return False
    else:
        return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    get_api = get_api_answer(current_timestamp)
    check_api = check_response(get_api)
    while True:
        if not check_tokens():
            break
        try:
            response = parse_status(check_api)
            message_set = set()
            if response not in message_set:
                message_set.add(response)
                send_message(bot, response)
                logging.info(response)
            else:
                logging.debug(response)
            current_timestamp = get_api['current_date']
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            time.sleep(RETRY_TIME)
        else:
            get_api = get_api_answer(current_timestamp)
            check_api = check_response(get_api)


if __name__ == '__main__':
    main()
