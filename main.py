#!/usr/bin/env python3

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s: %(message)s")

import asyncio
from datetime import datetime, timedelta
import os

from aiohttp import ClientSession

from renault_api.credential_store import FileCredentialStore
from renault_api.renault_vehicle import RenaultVehicle
from renault_api.kamereon.helpers import DAYS_OF_WEEK
from renault_api.kamereon.models import ChargeSchedule, ChargeDaySchedule, HvacSchedule, HvacDaySchedule
from renault_api.cli import renault_settings, renault_vehicle
from renault_api.cli.__main__ import _check_for_debug

CHARGE_SCHEDULE_TO_CONTROL = 5
HVAC_SCHEDULE_TO_CONTROL = 5

def _hvac_schedule_needs_modification(today, tomorrow, schedule, logger):
    for day in DAYS_OF_WEEK:
        if day != tomorrow:
            # if a day != tomorrow has a schedule, we need to clear it
            if getattr(schedule, day) is not None:
                needs_modification = True

    # tomorrow should have a schedule
    if (tomorrow_schedule := getattr(schedule, tomorrow)) is not None:
        # and its time should be 15:15 @ 15min
        if tomorrow_schedule.readyAtTime != "T15:15Z":
            logger.debug("Tomorrow (%s) has a schedule other than ours! (T15:15Z)", tomorrow)
            return True
    # if there was no schedule at all, we need one
    else:
        logger.debug("Tomorrow (%s) had no schedule", tomorrow)
        return True

    # and it should be activated
    if not schedule.activated:
        logger.debug("Schedule id %s was not active", HVAC_SCHEDULE_TO_CONTROL)
        return True

    return False

def _build_hvac_schedule(today, tomorrow, logger):
    schedule = HvacSchedule(raw_data={},
            id=HVAC_SCHEDULE_TO_CONTROL,
            activated=True,
            monday=None,
            tuesday=None,
            wednesday=None,
            thursday=None,
            friday=None,
            saturday=None,
            sunday=None,
            )
    tomorrow_schedule = HvacDaySchedule(raw_data={}, readyAtTime="T15:15Z")
    setattr(schedule, tomorrow, tomorrow_schedule)
    return schedule

async def _check_and_update_hvac_schedule(today, tomorrow, vehicle):
    logger = logging.getLogger("hvac")

    current_schedule_data = await vehicle.get_hvac_settings()
    current_schedule = current_schedule_data.schedules[HVAC_SCHEDULE_TO_CONTROL-1]
    logger.debug("Found current hvac schedule: %s", current_schedule)

    if _hvac_schedule_needs_modification(today, tomorrow, current_schedule, logger):
        new_schedule = _build_hvac_schedule(today, tomorrow, logger)
        current_schedule_data.schedules[HVAC_SCHEDULE_TO_CONTROL-1] = new_schedule
        logger.info("Modifications needed! Will send new schedules %s", current_schedule_data.schedules)
        await vehicle.set_hvac_schedules(current_schedule_data.schedules)
    else:
        logger.debug("No update needed")

def _charge_schedule_needs_modification(today, tomorrow, schedule, logger):
    for day in DAYS_OF_WEEK:
        if day != tomorrow:
            # if a day != tomorrow has a schedule, we need to clear it
            if getattr(schedule, day) is not None:
                needs_modification = True

    # tomorrow should have a schedule
    if (tomorrow_schedule := getattr(schedule, tomorrow)) is not None:
        # and its time should be 15:15 @ 15min
        if tomorrow_schedule.startTime != "T15:15Z" or tomorrow_schedule.duration != 15:
            logger.debug("Tomorrow (%s) has a schedule other than ours! (T15:15Z for 15min)", tomorrow)
            return True
    # if there was no schedule at all, we need one
    else:
        logger.debug("Tomorrow (%s) had no schedule", tomorrow)
        return True

    # and it should be activated
    if not schedule.activated:
        logger.debug("Schedule id %s was not active", CHARGE_SCHEDULE_TO_CONTROL)
        return True

    return False

def _build_charge_schedule(today, tomorrow, logger):
    schedule = ChargeSchedule(raw_data={},
            id=CHARGE_SCHEDULE_TO_CONTROL,
            activated=True,
            monday=None,
            tuesday=None,
            wednesday=None,
            thursday=None,
            friday=None,
            saturday=None,
            sunday=None,
            )
    tomorrow_schedule = ChargeDaySchedule(raw_data={}, startTime="T15:15Z", duration="15")
    setattr(schedule, tomorrow, tomorrow_schedule)
    return schedule

async def _check_and_update_charge_schedule(today, tomorrow, vehicle):
    logger = logging.getLogger("charge")

    current_schedule_data = await vehicle.get_charging_settings()
    current_schedule = current_schedule_data.schedules[CHARGE_SCHEDULE_TO_CONTROL-1]
    logger.debug("Found current charge schedule: %s", current_schedule)

    if _charge_schedule_needs_modification(today, tomorrow, current_schedule, logger):
        new_schedule = _build_charge_schedule(today, tomorrow, logger)
        current_schedule_data.schedules[CHARGE_SCHEDULE_TO_CONTROL-1] = new_schedule
        logger.info("Modifications needed! Will send new schedules %s", current_schedule_data.schedules)
        await vehicle.set_charge_schedules(current_schedule_data.schedules)
    else:
        logger.debug("No update needed")


async def periodic():
    logging.getLogger("charge").setLevel(logging.DEBUG)
    logging.getLogger("hvac").setLevel(logging.DEBUG)
    logger = logging.getLogger("scheduler")
    logger.setLevel(logging.DEBUG)

    while True:
        today = DAYS_OF_WEEK[datetime.now().weekday()]
        tomorrow = DAYS_OF_WEEK[(datetime.now()+timedelta(days=1)).weekday()]
        logger.info("Running! Found today=%s, tomorrow=%s", today, tomorrow)

        credential_file = os.path.expanduser(renault_settings.CREDENTIAL_PATH)
        if not os.path.isfile(credential_file):
            logger.error("Cannot find credentials file '%s'! Are you logged in? If not, try starting 'renault-api status' inside of the docker container (see: 'docker exec') and follow the log-in procedure. This script will re-try after 30s.", credential_file)
            await asyncio.sleep(30)
            continue

        websession = ClientSession()
        fake_ctx = {}
        fake_ctx["credential_store"] = FileCredentialStore(
            credential_file
        )
        vehicle: RenaultVehicle = await renault_vehicle.get_vehicle(
            websession=websession, ctx_data=fake_ctx
        )

        await _check_and_update_charge_schedule(today, tomorrow, vehicle)
        await _check_and_update_hvac_schedule(today, tomorrow, vehicle)

        await websession.close()

        logger.info("Sleeping ...")
        await asyncio.sleep(60*60*4)

loop = asyncio.get_event_loop()
task = loop.create_task(periodic())
try:
    loop.run_until_complete(task)
except asyncio.CancelledError:
    pass
