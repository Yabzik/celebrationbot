from app.db import HolidayCache
from app.scrapers.scraper import Scraper

import aiohttp
import asyncio
import random
import json
import aiofiles

from bs4 import BeautifulSoup

from pathlib import Path

import os
from dotenv import load_dotenv

load_dotenv()


class WomboScraper(Scraper):
    async def download_images(self, holiday_cache: HolidayCache, count=20):
        path = Path(f"./cache/{holiday_cache.directory}")
        path.mkdir(parents=True, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            await self._sign_up(session)

            wombo_styles = await self.get_wombo_styles(session)

            for i in range(count):
                url = await self.get_url_from_wombo(
                    session, holiday_cache.name,
                    random.choice(wombo_styles)['id'])

                await self.save_file(session, url, path / f'{i}.jpg')

        return len(list(path.glob('*')))

    async def save_file(self, session: aiohttp.ClientSession, url, path):
        r = await session.get(url)

        async with aiofiles.open(path, 'wb') as f:
            async for data in r.content:
                await f.write(data)

    async def _sign_up(self, session: aiohttp.ClientSession):
        r = await session.post(
            'https://identitytoolkit.googleapis.com'
            f'/v1/accounts:signUp?key={os.getenv("WOMBO_GOOGLE_KEY")}')

        r = await r.json()

        self.auth_token = r['idToken']

    async def get_wombo_styles(self, session):
        page = await session.get('https://www.wombo.art/create')
        contents = await page.text()

        soup = BeautifulSoup(contents, 'lxml')
        script = soup.find_all("script")[-1].get_text()
        script = json.loads(script)

        return script['props']['pageProps']['artStyles']

    async def get_url_from_wombo(self, session, holiday_title, style):
        headers = {'Authorization': f'bearer {self.auth_token}'}

        await session.options('https://paint.api.wombo.ai/api/tasks')
        tasks_info = await session.post(
            'https://paint.api.wombo.ai/api/tasks',
            json={'premium': False}, headers=headers)
        tasks_info = await tasks_info.json()

        if ('detail' in tasks_info) and \
                tasks_info['detail'] == 'User has been rate-limited':
            print('Rate limited....')
            await asyncio.sleep(25)
            return await self.get_url_from_wombo(session, holiday_title, style)

        task_id = tasks_info['id']

        await session.options(
            f'https://paint.api.wombo.ai/api/tasks/{task_id}')
        await session.put(
            f'https://paint.api.wombo.ai/api/tasks/{task_id}',
            json={
                "input_spec": {
                    "prompt": str(holiday_title),
                    "style": int(style),
                    "display_freq": 10}
                }, headers=headers)

        while True:
            task_state = await session.get(
                f'https://paint.api.wombo.ai/api/tasks/{task_id}',
                headers=headers)
            task_state = await task_state.json()
            if task_state['state'] != 'completed':
                await asyncio.sleep(1)
            else:
                break

        task_state = await session.get(
            f'https://paint.api.wombo.ai/api/tasks/{task_id}', headers=headers)
        task_state = await task_state.json()

        result_url = task_state['result']['final']

        return result_url
