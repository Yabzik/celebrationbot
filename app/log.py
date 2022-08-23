import sys
import os

import logging
import logging.handlers as handlers

if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(level=logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
file_handler = handlers.TimedRotatingFileHandler(
    'logs/app.log', when='D', interval=1, backupCount=14)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)


def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
