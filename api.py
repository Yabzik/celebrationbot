from fastapi import FastAPI, HTTPException, BackgroundTasks
import fastapi.responses
import datetime
from uuid import UUID
import random

import app.holiday as holiday
import app.db as db
from tortoise.contrib.fastapi import register_tortoise

import os
from dotenv import load_dotenv

load_dotenv()

holiday_controller = holiday.HolidayController()

description = """
Holiday API allows you to get a list of holidays for a particular day
and greeting cards images. 🎉
"""

app = FastAPI(
    title="Holiday API",
    description=description,
    version="0.0.1",
    contact={
        "name": "Yaroslav Bielash",
        "url": "https://yabzik.online",
        "email": "me@yabzik.online",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },)


async def process_query(image_query: db.ImageQuery):
    try:
        image = await holiday_controller.get_prepared_image_by_query(
            image_query.query)
        await holiday_controller._save_query_to_file(
            f'{image_query.uuid}.png', image)

        image_query.ready = True
        await image_query.save()
    except Exception:
        if image_query.retries < 5:
            image_query.retries += 1
            await image_query.save()

            return await process_query(image_query)


@app.get(
    '/{date}/holidays',
    summary="Get holidays by date"
)
async def get_date_holidays(
    date: datetime.date
):
    if date.year < 2010:
        raise HTTPException(
            status_code=400,
            detail="Dates before 2010 are not supported")
    holidays = await holiday_controller.get_date_holidays(date)
    return {
        'day': holidays['day'],
        'holidays': holidays['holidays']
    }


@app.get(
    '/{date}/image',
    summary="Get random holiday greeting image by date",
    response_description="Image query identifier",
)
async def get_date_image(
    date: datetime.date,
    background_tasks: BackgroundTasks
):
    if date.year < 2010:
        raise HTTPException(
            status_code=400,
            detail="Dates before 2010 are not supported")

    holidays = await holiday_controller.get_date_holidays(date)
    holiday = random.choice(holidays['holidays'])

    query = await db.ImageQuery.create(query=holiday)

    background_tasks.add_task(process_query, query)

    return {
        'day': holidays['day'],
        'holiday': holiday,
        'query': query.uuid
    }


@app.get(
    '/image',
    summary="Get holiday greeting image by string",
    response_description="Image query identifier",
)
async def get_query_holidays(
    query: str,
    background_tasks: BackgroundTasks
):

    query = await db.ImageQuery.create(query=query)

    background_tasks.add_task(process_query, query)

    return {
        'query': query.uuid
    }


@app.get(
    '/queries/{id}',
    summary="Get query status"
)
async def get_query_status(
    id: UUID
):
    query = await db.ImageQuery.get_or_none(uuid=id)

    if not query:
        raise HTTPException(
            status_code=404,
            detail="This query was not found")

    return {
        'id': query.uuid,
        'query': query.query,
        'ready': query.ready,
        'error': (query.retries >= 5)
    }


@app.get(
    '/queries/{id}/image',
    summary="Get query image (if ready)",
    responses={
        200: {
            "content": {"image/png": {}}
        },
        400: {
            "content": {"application/json": {}}
        },
        404: {
            "content": {"application/json": {}}
        }
    },
    response_class=fastapi.responses.Response
)
async def get_query_image(
    id: UUID
):
    print(str(id))
    query = await db.ImageQuery.get_or_none(uuid=id)

    if not query:
        raise HTTPException(
            status_code=404,
            detail="This query was not found")
    if not query.ready:
        raise HTTPException(
            status_code=400,
            detail="This query has not yet been processed")

    img = await holiday_controller._read_query_from_file(f'{query.uuid}.png')
    return fastapi.responses.Response(content=img, media_type="image/png")

register_tortoise(
    app,
    db_url=os.getenv('DB_URL'),
    modules={"models": [db]},
    generate_schemas=True,
    add_exception_handlers=True,
)
