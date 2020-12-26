#!/usr/bin/env python3

import logging
logging.basicConfig(level=logging.DEBUG)

import asyncio
from datetime import datetime, timedelta
import os

from aiohttp import ClientSession

from renault_api.credential_store import FileCredentialStore
from renault_api.renault_vehicle import RenaultVehicle
from renault_api.kamereon.helpers import DAYS_OF_WEEK
from renault_api.kamereon.models import ChargeDaySchedule
from renault_api.cli import renault_settings, renault_vehicle
from renault_api.cli.__main__ import _check_for_debug

CHARGE_SCHEDULE_TO_CONTROL = 5

logger = logging.getLogger("ZEScheduleShifter")

async def check_and_update_charge_schedule():
    today = DAYS_OF_WEEK[datetime.now().weekday()]
    tomorrow = DAYS_OF_WEEK[(datetime.now()+timedelta(days=1)).weekday()]
    fake_ctx = {}
    websession = ClientSession()

    fake_ctx["credential_store"] = FileCredentialStore(
        os.path.expanduser(renault_settings.CREDENTIAL_PATH)
    )

    vehicle: RenaultVehicle = await renault_vehicle.get_vehicle(
        websession=websession, ctx_data=fake_ctx
    )

    current_schedule_data = await vehicle.get_charging_settings()
    schedule = current_schedule_data.schedules[CHARGE_SCHEDULE_TO_CONTROL-1]
    logger.debug("Found current charge schedule: %s", schedule)

    needs_modification = False
    for day in DAYS_OF_WEEK:
        if day != tomorrow:
            if getattr(schedule, day) is not None:
                needs_modification = True
                logger.debug("Had to clear day %s", day)
                setattr(schedule, day, None)

    if (tomorrow_schedule := getattr(schedule, tomorrow)) is not None:
        logger.debug("Tomorrow has a schedule defined")
        if tomorrow_schedule.startTime != "T15:15Z" or tomorrow_schedule.duration != 15:
            logger.debug("Tomorrow has a schedule other than ours! (T15:15Z for 15min)")
            needs_modification = True
            setattr(schedule, tomorrow, ChargeDaySchedule(raw_data={}, startTime="T15:15Z", duration="15"))
        else:
            logger.debug("Tomorrows schedule was ours")
    else:
        logger.debug("Tomorrow had no schedule, setting one ...")
        needs_modification = True
        setattr(schedule, tomorrow, ChargeDaySchedule(raw_data={}, startTime="T15:15Z", duration="15"))

    if not schedule.activated:
        logger.debug("Schedule id %s was not active, activating", CHARGE_SCHEDULE_TO_CONTROL)
        needs_modification = True
        schedule.activated = True

    if needs_modification:
        logger.info("Modifications needed! Will send new schedules %s", current_schedule_data.schedules)
        await vehicle.set_charge_schedules(current_schedule_data.schedules)

    await websession.close()

async def periodic():
    while True:
        await check_and_update_charge_schedule()
        logger.info("Sleeping ...")
        await asyncio.sleep(60*60*4)

loop = asyncio.get_event_loop()
task = loop.create_task(periodic())
try:
    loop.run_until_complete(task)
except asyncio.CancelledError:
    pass
