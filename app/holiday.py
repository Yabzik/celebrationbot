import aiohttp
import asyncio
import lxml.html
import datetime
import random
import io

from PIL import Image, ImageFont, ImageDraw

import pymorphy2
from pyphrasy.inflect import PhraseInflector

from google_images_download import google_images_download

from app.db import HolidayCache

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

import tortoise

import app.log

import os
from dotenv import load_dotenv

load_dotenv()


class HolidayController:
    def __init__(self):
        self.logger = app.log.get_logger('holiday_controller')
        self.banned_parts = os.getenv('BANNED_PARTS').split(',')

        self.downloader = google_images_download.googleimagesdownload()

    async def _filter_holidays(self, holidays):
        result = []
        for holiday in holidays:
            if any(substring in holiday.lower() for substring
                    in self.banned_parts):
                self.logger.info(
                    'Found banned part in "%s", skipping',
                    holiday)
            else:
                result.append(holiday)
        return result

    async def get_date_prepared_image(self, date):
        holidays = await self.get_date_holidays(date)
        holiday = random.choice(holidays['holidays'])

        holiday_cache, _ = await HolidayCache.get_or_create(name=holiday)
        holiday_cache.accessed_at = tortoise.timezone.now()
        await holiday_cache.save()

        if holiday_cache.images_count <= 0:
            images_count = await self.download_images(holiday_cache, 5)
            holiday_cache.images_count = images_count
            await holiday_cache.save()

        loop = asyncio.get_event_loop()
        thread_pool = ThreadPoolExecutor()
        resulting_image = await loop.run_in_executor(
            thread_pool,
            partial(
                self._prepare_image_sync,
                holiday_cache.name,
                holiday_cache.directory
            )
        )
        return resulting_image, holidays['day']

    def _get_greeting(self, holiday):
        morph = pymorphy2.MorphAnalyzer()
        inflector = PhraseInflector(morph)
        return 'С ' + inflector.inflect(holiday, 'ablt')

    def _get_random_date(self):
        year = datetime.datetime.now().year
        # try to get a date
        try:
            return datetime.datetime.strptime(
                '{} {}'.format(random.randint(1, 366), year), '%j %Y').date()
        # if the value happens to be in the leap year range, try again
        except ValueError:
            return self.get_random_date()

    def _text_wrap(self, text, font, max_width):
        lines = []
        # If the width of the text is smaller than image width
        # we don't need to split it, just add it to the lines array
        # and return
        if font.getsize(text)[0] <= max_width:
            lines.append(text)
        else:
            # split the line by spaces to get words
            words = text.split(' ')
            i = 0
            # append every word to a line
            # while its width is shorter than image width
            while i < len(words):
                line = ''
                while (
                        i < len(words) and
                        font.getsize(line + words[i])[0] <= max_width):
                    line = line + words[i] + " "
                    i += 1
                if not line:
                    line = words[i]
                    i += 1
                # when the line gets longer than the
                # max width do not append the word,
                # add the line to the lines array
                lines.append(line)
        return lines

    def _draw_greeting_card(self, content, text):
        background = Image.open(io.BytesIO(content))
        overplay_dir = Path('./img')
        overlay_path = random.choice(list(overplay_dir.glob('*')))

        overlay = Image.open(overlay_path.resolve())
        ow, oh = overlay.size

        ow = random.randint(10, ow)
        oh = random.randint(10, oh)
        overlay = overlay.resize((ow, oh))

        bw, bh = background.size

        x = random.randint(0, abs(bw-ow))
        y = random.randint(0, abs(bh-oh))

        background.paste(overlay, (x, y), overlay)

        font = ImageFont.truetype("lobster.ttf", int(bw/16))
        draw = ImageDraw.Draw(background)
        lines = self._text_wrap(text, font, bw)
        line_height = font.getsize('hg')[1]

        # te_x = 10
        te_y = bh - (len(lines)*line_height)

        for line in lines:
            tfw, tfh = draw.textsize(line, font=font)
            draw.text((int((bw-tfw)/2)-1, te_y-1), line, (0, 0, 0), font=font)
            draw.text(
                (int((bw-tfw)/2), te_y),
                line, (255, 255, 255), font=font)
            te_y += line_height

        temp = io.BytesIO()
        background.save(temp, format="png")
        return temp.getvalue()

    def _prepare_image_sync(self, holiday, directory):
        path = Path(f"./cache/{directory}")
        image_path = random.choice(list(path.glob('*')))

        greeting = self._get_greeting(holiday)

        with open(image_path.resolve(), 'rb') as f:
            content = f.read()
            return self._draw_greeting_card(content, greeting)

    async def get_date_holidays(self, date: datetime.date):
        async with aiohttp.ClientSession() as session:
            url = 'https://www.calend.ru/day/'
            url += f'{date.year}-{date.month}-{date.day}'
            async with session.get(url) as resp:
                tree = lxml.html.fromstring(await resp.text())

                holidays = tree.xpath(
                    "//div[@class='block holidays']"
                    "/ul[@class='itemsNet']/li//div[@class='caption']"
                    "/span[@class='title']/a/text()")
                today = tree.xpath("//div[@class='block main']"
                                   "/h1[@class='day_title']/text()")[1]

                today = today.replace("\xa0", '').replace("\n  ", '')

                return {
                        'day': today,
                        'holidays': await self._filter_holidays(holidays)
                    }

    async def update_holidays(self):
        self.today = await self.get_date_holidays(datetime.date.today())

        self.logger.info(
            'Updated today holidays (%s): %s',
            self.today['day'], str(self.today['holidays']))

        for holiday in self.today['holidays']:
            holiday_cache, _ = await HolidayCache.get_or_create(name=holiday)
            holiday_cache.accessed_at = tortoise.timezone.now()
            await holiday_cache.save()

            if holiday_cache.images_count <= 0:
                images_count = await self.download_images(holiday_cache)
                holiday_cache.images_count = images_count
                await holiday_cache.save()

    async def download_images(self, holiday_cache: HolidayCache, count=20):
        loop = asyncio.get_event_loop()
        thread_pool = ThreadPoolExecutor()

        downloaded_count = await loop.run_in_executor(
            thread_pool,
            partial(
                self._download_images_sync,
                holiday_cache.name,
                holiday_cache.directory,
                count
            )
        )
        return downloaded_count

    def _download_images_sync(self, holiday_title, path_suffix, count):
        path = Path(f"./cache/{path_suffix}")
        path.mkdir(parents=True, exist_ok=True)

        self.downloader.download(
            {
                'keywords': str(holiday_title),
                'limit': int(count),
                'output_directory': 'cache',
                'image_directory': str(path_suffix),
                'silent_mode': True
            }
        )

        return len(list(path.glob('*')))
