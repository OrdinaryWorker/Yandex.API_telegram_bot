import logging
import os

import requests
import time

from telegram import Bot
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)


TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """ Проверяет доступность переменных окружения """
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def get_api_answer(current_timestamp):
    """ Делает запрос к эндпоинту API Практикум.Домашка"""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logger.info('Отправка запроса к API-сервису')
        homework_status = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params)
        if homework_status.status_code != 200:
            message = 'API не ответил'
            logger.warning(message)
            raise Exception(message)

        return homework_status.json()
        # возвращает словарь вида {"homeworks": [...], "current_date":1634074965}
    except Exception as error:
        message = f'Ошибка при запросе к основному API: {error}'
        logger.error(message)
        return message


def check_response(response):
    """ Проверяет ответ API Практикум.Домашка на корректность"""
    if isinstance(response, dict):
        if 'homeworks' and 'current_date' in response.keys():
            logger.info(f'Получен валидный ответ от API Практикум.Домашка')
            return response['homeworks']
            # возвращает список работ, который может быть пустым
        else:
            message = 'Ответ от API Практикум.Домашка не валиден'
            logger.error(message)
            return message
    else:
        return response

def parse_status(homework):
    """ Проверяет статус домашней роботы и возвращает расшифровку статуса """
    logging.info('Проверка статуса домашней работы')
    # получаю на вход список или сообщение об ошибке
    if isinstance(homework, dict) and homework:
        try:
            homework_name = homework[0].get('homework_name')
            homework_status = homework[0].get('status')
        except KeyError:
            message = f'В полученном ответе отсутствует название работы'
            logger.error(message)
            return message
        try:
            verdict = HOMEWORK_VERDICTS[homework_status]
        except KeyError:
            message = f'Недокументированный статус домашней работы:{homework_status}'
            logger.error(message)
            return message
        logging.info('Получен валидный статус работы {}'.format(homework_name))
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    elif isinstance(homework, list):
        message = 'Получен пустой список работ'
        logger.info = message
        return ''
    else:
        return homework


def send_message(bot, message):
    """ Отправляет сообщение боту в телеграмм """
    last_message = ''
    if last_message != message:
        try:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            logging.info('Телеграм бот отправил сообщение в чат')
        except Exception as error:
            message = f'Сбой в работе телеграм-бота: {error}'
            logger.error(message)


def main():
    """Основная логика работы бота."""

    if check_tokens():
        bot = Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
    else:
        message = 'Переменные окружения не доступны'
        logger.critical(message)
        raise Exception(message)
    previous_report = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response['current_date']
            homeworks_list = check_response(response)
            verdict = parse_status(homeworks_list)
            current_report = verdict
            if current_report != previous_report:
                previous_report = current_report
                send_message(bot, current_report)
            else:
                logger.debug(
                    'Статус работы не изменился, сообщение не отправлено'
                )
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()

