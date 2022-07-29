import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(funcName)s - %(levelname)s - %(message)s',
    level=logging.INFO
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


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def get_api_answer(current_timestamp: int) -> dict:
    """Делает запрос к эндпоинту API Практикум.Домашка."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logger.info('Отправка запроса к API-сервису')
        homework_status = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params)
    except Exception as error:
        message = f'Ошибка при запросе к основному API: {error}, ' \
                  f'{ENDPOINT}, {HEADERS}'
        logger.error(message)
        raise Exception(message)
    if homework_status.status_code != HTTPStatus.OK:
        message = (f'Не удалось установить соединение с API-сервисом '
                   f'{homework_status.url}, {homework_status.status_code}')
        logger.error(message)
        raise Exception(message)
    try:
        homework_status = homework_status.json()
    except Exception as error:
        message = f'Ошибка при обработке json-файла: {error}, '
        logger.error(message)
        raise Exception(message)

    return homework_status


def check_response(response: dict) -> list:
    """Проверяет ответ API Практикум.Домашка на корректность."""
    logger.info('Проверка валидности полученного ответа от API')
    if not isinstance(response, dict):
        message = 'Ответ от API Практикум.Домашка не является словарем'
        logger.error(message)
        raise TypeError(message)

    homeworks_list = response.get('homeworks')
    if not isinstance(homeworks_list, list):
        message = 'В ответе от API нет необходимого ключа "homeworks"'
        logger.error(message)
        raise KeyError(message)

    if 'current_date' not in response:
        message = 'В ответе от API нет необходимого ключа "current_date"'
        logger.error(message)
        raise KeyError(message)

    if not isinstance(homeworks_list, list):
        message = 'Значение ключа "homeworks" не является списком'
        logger.error(message)
        raise TypeError(message)

    return homeworks_list


def parse_status(homework: dict) -> str:
    """Проверяет статус домашней роботы и возвращает расшифровку статуса."""
    logging.info('Проверка статуса домашней работы')
    if not isinstance(homework, dict):
        message = 'Значение ключа "homeworks" не является словарем'
        logger.error(message)
        raise TypeError(message)

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not (homework_name and homework_status):
        message = ('В ответе от API нет необходимой ключей '
                   '"homework_name" и "status"')
        logger.error(message)
        raise KeyError(message)

    if homework_status not in HOMEWORK_VERDICTS:
        message = f'Недокументированный статус домашней работы:{homework_name}'
        logger.error(message)
        raise KeyError(message)
    logging.info('Получен валидный статус работы {}'.format(homework_name))
    return (f'Изменился статус проверки работы "{homework_name}".'
            f' {HOMEWORK_VERDICTS[homework_status]}')


def send_message(bot, message: str) -> None:
    """Отправляет сообщение боту в телеграм."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info('Телеграм бот отправил сообщение в чат')
    except Exception as error:
        message = f'Сбой в работе телеграм-бота: {error}'
        logger.error(message)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Переменные окружения не доступны'
        logger.critical(message)
        sys.exit(message)

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    previous_report = {
        'message_name': '',
        'output_text': ''
    }
    current_report = {
        'message_name': '',
        'output_text': ''
    }
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response['current_date']
            homeworks_list = check_response(response)
            if homeworks_list:
                verdict = parse_status(homeworks_list[0])
                current_report['message_name'] = verdict.split()[4]
                current_report['output_text'] = verdict
            else:
                message = 'Статус работы не изменился'
                logger.debug(message)
                current_report['output_text'] = message

            if current_report != previous_report:
                send_message(bot, current_report['output_text'])
                previous_report = current_report.copy()
            else:
                logger.debug(
                    'Статус работы не изменился, сообщение не отправлено'
                )

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            current_report['name_message'] = 'Error'
            current_report['output_text'] = message
            if current_report != previous_report:
                send_message(bot, current_report['output_text'])
                previous_report = current_report.copy()

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
