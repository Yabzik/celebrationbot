import os

from loguru import logger

if not os.path.exists('logs'):
    os.makedirs('logs')

logger.add("logs/app.log", rotation="1 day")

def get_logger(logger_name):
    return logger
