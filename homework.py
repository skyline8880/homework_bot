import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import (ConnectionError, InvalidURL, RequestException,
                                 Timeout)

from exceptions import (BreakSendMessage, MissedKey, Not200Status, NotListType,
                        WrongDocType, NotDictType, NoInfo)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 10
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
handler = RotatingFileHandler(
    'homework_check.log',
    maxBytes=50000000,
    backupCount=5
)


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        send = bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info('Сообщение успешно отправлено')
        return send
    except BreakSendMessage:
        raise BreakSendMessage('Не удалось отправить сообщение')


def get_api_answer(current_timestamp):
    """Запрос и обработка информации с сервера."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        api_answer = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if api_answer.status_code != 200:
            raise Not200Status(f'Сбой, при переходе по ссылке: {ENDPOINT}')
        return api_answer.json()
    except ConnectionError:
        print('Отсутсвует соединение')
    except InvalidURL:
        print('Невереный адрес')
    except Timeout:
        print('Время ожидания истекло')
    except RequestException:
        print('Сбой при подключении')


def check_response(response):
    """Проверка, полученных данных."""
    if isinstance(response, dict):
        if 'homeworks' not in response.keys():
            raise MissedKey('Отсутствует ключевое значение - "homeworks"')
    if not isinstance(response['homeworks'], list):
        raise NotListType('Отсутствует тип данных - "список"')
    if not response['homeworks']:
        raise NoInfo('Нет данных')
    return response['homeworks'][0]


def parse_status(homework):
    """Извлечение, необходимой нам, информации."""
    if not isinstance(homework, dict):
        raise NotDictType('Ответ в неверном типе данных')
    if ('homework_name' not in homework.keys()
            or 'status' not in homework.keys()):
        raise MissedKey('Отсутствует ключ, "homework_name" или "status"')
    if homework['status'] not in HOMEWORK_STATUSES.keys():
        raise WrongDocType('Недопустимое значение ключа - "status"')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    return (f'Изменился статус проверки работы '
            f'"{homework_name}". {HOMEWORK_STATUSES[homework_status]}')


def check_tokens():
    """Проверка наличия необходимых переменных."""
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.critical('Отсутствуют, необходимые переменные')
        return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    error_messages = []
    if check_tokens():
        while True:
            try:
                get_api = get_api_answer(current_timestamp)
                check_api = check_response(get_api)
                response = parse_status(check_api)
                logging.debug(response)
                send_message(bot, response)
                logging.info(response)
                current_timestamp = get_api['current_date']
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                if (message not in error_messages
                        or message != error_messages[0]):
                    error_messages.append(message)
                    send_message(bot, message)
                    logging.info(message)
                logging.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
