import app.db as db
import app.holiday as holiday
import app.log

from tortoise import Tortoise, run_async

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

import aiogram

import datetime
import random
import os
from dotenv import load_dotenv

load_dotenv()

scheduler = None
holiday_controller = holiday.HolidayController()
logger = app.log.get_logger('main')

bot = aiogram.Bot(token=os.getenv('TG_TOKEN'))
dp = aiogram.Dispatcher(bot)


@logger.catch
@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: aiogram.types.Message):
    await message.reply(('Привет! Теперь каждый день я '
                         'буду сообщать тебе о праздниках! '
                         'Если захочешь отключить рассылку - напиши /off'))

    subscriber, _ = await db.Subscriber.get_or_create(
        telegram_id=message.from_user.id,
        defaults={'name': message.from_user.full_name})
    logger.info(f'{subscriber} sent /start')
    await _create_daily_job(subscriber)
    subscriber.enabled = True
    await subscriber.save()


@logger.catch
@dp.message_handler(commands=['off'])
async def send_off(message: aiogram.types.Message):
    subscriber = await db.Subscriber.get(telegram_id=message.from_user.id)
    if subscriber.enabled:
        subscriber.enabled = False
        await subscriber.save()

        if scheduler.get_job(f'daily_{subscriber.telegram_id}'):
            scheduler.remove_job(f'daily_{subscriber.telegram_id}')

        await message.reply('Отключил рассылку!')
        logger.info(f'{subscriber} disabled subscription')
    else:
        await message.reply('Рассылка уже отключена!')


@logger.catch
@dp.message_handler(commands=['today'])
async def send_today(message: aiogram.types.Message):
    msg = await message.reply('⏳ Ожидайте...')
    img, _ = await holiday_controller.get_date_prepared_image(
        datetime.date.today())

    await bot.delete_message(msg.chat.id, msg.message_id)
    await message.reply_photo(img)


@logger.catch
@dp.message_handler(commands=['random'])
async def send_random(message: aiogram.types.Message):
    msg = await message.reply('⏳ Ожидайте...')
    img, day = await holiday_controller.get_date_prepared_image(
        holiday_controller._get_random_date())

    await bot.delete_message(msg.chat.id, msg.message_id)
    await message.reply_photo(img, caption=day)


@logger.catch
async def _send_daily(telegram_id):
    try:
        img, _ = await holiday_controller.get_date_prepared_image(
            datetime.date.today())
        await bot.send_photo(telegram_id, img)
    except aiogram.utils.exceptions.BotBlocked:
        subscriber = await db.Subscriber.get(telegram_id=telegram_id)
        subscriber.enabled = False
        await subscriber.save()
        logger.info(f'Subscriber {subscriber} blocked bot, disabling...')
    except Exception:
        subscriber = await db.Subscriber.get(telegram_id=telegram_id)
        logger.error(f'Failed sending daily card to {subscriber}...')
        scheduler.add_job(
            _send_daily, 'date',
            run_date=(datetime.datetime.now() + datetime.timedelta(minutes=5)),
            args=[subscriber.telegram_id])
    else:
        subscriber = await db.Subscriber.get(telegram_id=telegram_id)
        logger.debug(f'Creating daily job for {subscriber}')
        await _create_daily_job(subscriber)
        logger.info(f'Sent daily card to {subscriber}')


@logger.catch
async def _create_daily_job(subscriber: db.Subscriber):
    if not scheduler.get_job(f'daily_{subscriber.telegram_id}'):
        tomorrow_datetime = datetime.datetime.now() + \
            datetime.timedelta(days=1)
        tomorrow_datetime = tomorrow_datetime.replace(
            hour=random.randint(9, 17), minute=random.randint(0, 59))
        scheduler.add_job(
            _send_daily, 'date',
            id=f'daily_{subscriber.telegram_id}',
            run_date=tomorrow_datetime, args=[subscriber.telegram_id])

        logger.debug(f'Created daily job for {subscriber} '
                     f'({tomorrow_datetime})')
    else:
        logger.debug(f'Scheduler job exists for {subscriber}')


@logger.catch
async def run():
    await Tortoise.init(db_url=os.getenv('DB_URL'), modules={"models": [db]})
    await Tortoise.generate_schemas()

    await holiday_controller.update_holidays()


async def process_subscribers():
    enabled_subscribers = await db.Subscriber.filter(enabled=True)
    for subscriber in enabled_subscribers:
        await _create_daily_job(subscriber)


def start_scheduler():
    global scheduler

    jobstores = {
        'default': SQLAlchemyJobStore(
            url=os.getenv('DB_URL').replace('mysql', 'mysql+pymysql'))
    }
    # executors = {
    #     'default': ThreadPoolExecutor(20),
    #     'processpool': ProcessPoolExecutor(5)
    # }
    job_defaults = {
        'coalesce': False,
        'max_instances': 1
    }

    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        job_defaults=job_defaults,
        timezone='Europe/Zaporozhye')
    scheduler.start()

    if not scheduler.get_job('updateHolidays'):
        scheduler.add_job(
            holiday_controller.update_holidays,
            'cron', id='updateHolidays', hour=2, minute=0)


if __name__ == "__main__":
    run_async(run())
    start_scheduler()
    run_async(process_subscribers())
    # import asyncio
    # asyncio.get_event_loop().run_forever()
    aiogram.executor.start_polling(dp, skip_updates=True)
