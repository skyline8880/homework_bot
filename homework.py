import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import (ConnectionError, InvalidURL, RequestException,
                                 Timeout)

from exceptions import (MissedKey, NoInfo, Not200Status, NotDict,
                        NotDictResponse, NotListType, WrongDocType)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 2
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
    except telegram.error.TelegramError:
        raise telegram.error.TelegramError('Не удалось отправить сообщение')


def get_api_answer(current_timestamp):
    """Запрос и обработка информации с сервера."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    api_answer = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if api_answer.status_code != 200:
        raise Not200Status(f'Сбой, при переходе по ссылке: {ENDPOINT}')
    try:
        return api_answer.json()
    except ConnectionError:
        raise ConnectionError('Отсутствует соединение')
    except InvalidURL:
        raise InvalidURL('Неверный адрес')
    except Timeout:
        raise Timeout('Время ожидания истекло')
    except RequestException:
        raise RequestException('Сбой при подключении')


def check_response(response):
    """Проверка, полученных данных."""
    if not isinstance(response, dict):
        raise NotDictResponse('Ответ в неверном типе данных')
    if 'homeworks' not in response:
        raise MissedKey('Отсутствует ключевое значение - "homeworks"')
    if not isinstance(response['homeworks'], list):
        raise NotListType('Отсутствует тип данных - "список"')
    if not response['homeworks']:
        return response['homeworks']
    return response['homeworks'][0]


def parse_status(homework):
    """Извлечение, необходимой нам, информации."""
    if not homework:
        raise NoInfo('Нет новых данных')
    if not isinstance(homework, dict):
        raise NotDict('Ответ в неверном типе данных')
    if ('homework_name' not in homework
            or 'status' not in homework):
        raise MissedKey('Отсутствует ключ, "homework_name" или "status"')
    if homework['status'] not in HOMEWORK_STATUSES:
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
    error_message = ''
    if check_tokens():
        while True:
            try:
                get_api = get_api_answer(current_timestamp)
                check_api = check_response(get_api)
                response = parse_status(check_api)
                logging.debug(response)
                send_message(bot, response)
                current_timestamp = get_api['current_date']
            except NoInfo as i:
                logging.debug(i)
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                if message != error_message:
                    error_message = message
                    send_message(bot, error_message)
                logging.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
