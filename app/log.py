import os

from loguru import logger

import notifiers
from notifiers.logging import NotificationHandler

from dotenv import load_dotenv

load_dotenv()

params = {
    'chat_id': os.getenv('TG_NOTIFICATIONS_CHAT_ID'),
    'token': os.getenv('TG_TOKEN')
}

notifier = notifiers.get_notifier('telegram')
notifier.notify(message='The application is running!', **params)

handler = NotificationHandler('telegram', defaults=params)

if not os.path.exists('logs'):
    os.makedirs('logs')

logger.add("logs/app.log", rotation="1 day")
logger.add(handler, level="ERROR")


def get_logger(logger_name):
    return logger
