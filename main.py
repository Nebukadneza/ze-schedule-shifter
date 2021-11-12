#!/usr/bin/env python3
# pylint: disable=broad-except,missing-function-docstring,missing-module-docstring


import logging
import asyncio
from datetime import datetime, timedelta
import os
from aiohttp import ClientSession
from renault_api.credential_store import FileCredentialStore
from renault_api.renault_vehicle import RenaultVehicle
from renault_api.kamereon.helpers import DAYS_OF_WEEK
from renault_api.kamereon.models import (
    ChargeSchedule,
    ChargeDaySchedule,
    HvacSchedule,
    HvacDaySchedule,
)
from renault_api.cli import renault_settings, renault_vehicle

CHARGE_SCHEDULE_TO_CONTROL = int(os.getenv("CHARGE_SCHEDULE_TO_CONTROL", "5"))
HVAC_SCHEDULE_TO_CONTROL = int(os.getenv("HVAC_SCHEDULE_TO_CONTROL", "5"))


def _hvac_schedule_needs_modification(next_day, schedule, logger):
    for day in DAYS_OF_WEEK:
        if day != next_day:
            # if a day != next_day has a schedule, we need to clear it
            if getattr(schedule, day) is not None:
                return True

    # next_day should have a schedule
    if (next_day_schedule := getattr(schedule, next_day)) is not None:
        # and its time should be 15:15 @ 15min
        if next_day_schedule.readyAtTime != "T15:15Z":
            logger.debug(
                "Next Day (%s) has a schedule other than ours! (T15:15Z)", next_day
            )
            return True
    # if there was no schedule at all, we need one
    else:
        logger.debug("Next Day (%s) had no schedule", next_day)
        return True

    # and it should be activated
    if not schedule.activated:
        logger.debug("Schedule id %s was not active", HVAC_SCHEDULE_TO_CONTROL)
        return True

    return False


def _build_hvac_schedule(next_day):
    schedule = HvacSchedule(
        raw_data={},
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
    next_day_schedule = HvacDaySchedule(raw_data={}, readyAtTime="T15:15Z")
    setattr(schedule, next_day, next_day_schedule)
    return schedule


async def _check_and_update_hvac_schedule(next_day, vehicle):
    logger = logging.getLogger("hvac")

    if HVAC_SCHEDULE_TO_CONTROL == -1:
        logger.info("Not updating HvacSchedule, HVAC_SCHEDULE_TO_CONTROL is -1")
        return

    current_schedule_data = await vehicle.get_hvac_settings()
    current_schedule = current_schedule_data.schedules[HVAC_SCHEDULE_TO_CONTROL - 1]
    logger.debug("Found current hvac schedule: %s", current_schedule)

    if _hvac_schedule_needs_modification(next_day, current_schedule, logger):
        new_schedule = _build_hvac_schedule(next_day)
        current_schedule_data.schedules[HVAC_SCHEDULE_TO_CONTROL - 1] = new_schedule
        logger.info(
            "Modifications needed! Will send new schedules %s",
            current_schedule_data.schedules,
        )
        await vehicle.set_hvac_schedules(current_schedule_data.schedules)
    else:
        logger.debug("No update needed")


def _charge_schedule_needs_modification(next_day, schedule, logger):
    for day in DAYS_OF_WEEK:
        if day != next_day:
            # if a day != next_day has a schedule, we need to clear it
            if getattr(schedule, day) is not None:
                return True

    # next day should have a schedule
    if (next_day_schedule := getattr(schedule, next_day)) is not None:
        # and its time should be 15:15 @ 15min
        if next_day_schedule.startTime != "T15:15Z" or next_day_schedule.duration != 15:
            logger.debug(
                "Next Day (%s) has a schedule other than ours! (T15:15Z for 15min)",
                next_day,
            )
            return True
    # if there was no schedule at all, we need one
    else:
        logger.debug("Next Day (%s) had no schedule", next_day)
        return True

    # and it should be activated
    if not schedule.activated:
        logger.debug("Schedule id %s was not active", CHARGE_SCHEDULE_TO_CONTROL)
        return True

    return False


def _build_charge_schedule(next_day):
    schedule = ChargeSchedule(
        raw_data={},
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
    next_day_schedule = ChargeDaySchedule(
        raw_data={}, startTime="T15:15Z", duration="15"
    )
    setattr(schedule, next_day, next_day_schedule)
    return schedule


async def _check_and_update_charge_schedule(next_day, vehicle):
    logger = logging.getLogger("charge")

    if CHARGE_SCHEDULE_TO_CONTROL == -1:
        logger.info("Not updating ChargeSchedule, CHARGE_SCHEDULE_TO_CONTROL is -1")
        return

    current_schedule_data = await vehicle.get_charging_settings()
    current_schedule = current_schedule_data.schedules[CHARGE_SCHEDULE_TO_CONTROL - 1]
    logger.debug("Found current charge schedule: %s", current_schedule)

    if _charge_schedule_needs_modification(next_day, current_schedule, logger):
        new_schedule = _build_charge_schedule(next_day)
        current_schedule_data.schedules[CHARGE_SCHEDULE_TO_CONTROL - 1] = new_schedule
        logger.info(
            "Modifications needed! Will send new schedules %s",
            current_schedule_data.schedules,
        )
        await vehicle.set_charge_schedules(current_schedule_data.schedules)
    else:
        logger.debug("No update needed")


async def periodic():
    logging.getLogger("charge").setLevel(logging.DEBUG)
    logging.getLogger("hvac").setLevel(logging.DEBUG)
    logger = logging.getLogger("scheduler")
    logger.setLevel(logging.DEBUG)

    logging.info(
        "Will use charge schedule no. %s and hvac schedule no. %s",
        CHARGE_SCHEDULE_TO_CONTROL,
        HVAC_SCHEDULE_TO_CONTROL,
    )

    while True:
        today = DAYS_OF_WEEK[datetime.now().weekday()]
        next_day = DAYS_OF_WEEK[(datetime.now() + timedelta(days=4)).weekday()]
        logger.info("Running! Found today=%s, next_day=%s", today, next_day)

        credential_file = os.path.expanduser(renault_settings.CREDENTIAL_PATH)
        if not os.path.isfile(credential_file):
            logger.error(
                "Cannot find credentials file '%s'! Are you logged in? If not, try starting 'renault-api status' inside of the docker container (see: 'docker exec') and follow the log-in procedure. This script will re-try after 30s.",  #  pylint: disable=line-too-long
                credential_file,
            )
            await asyncio.sleep(30)
            continue

        websession = ClientSession()
        fake_ctx = {}
        fake_ctx["credential_store"] = FileCredentialStore(credential_file)

        try:
            vehicle: RenaultVehicle = await renault_vehicle.get_vehicle(
                websession=websession, ctx_data=fake_ctx
            )
        except Exception as exc:
            logger.warning("Could not acquire vehicle: %s! Will retry soon", exc)
            await asyncio.sleep(60 * 5)
            continue

        try:
            await _check_and_update_charge_schedule(next_day, vehicle)
        except Exception as exc:
            logger.warning(
                "Could not check or update charge schedule: %s! Will retry soon", exc
            )
            await asyncio.sleep(60 * 5)
            continue

        try:
            await _check_and_update_hvac_schedule(next_day, vehicle)
        except Exception as exc:
            logger.warning(
                "Could not check or update hvac schedule: %s! Will retry soon", exc
            )
            await asyncio.sleep(60 * 5)
            continue

        await websession.close()

        logger.info("Sleeping ...")
        await asyncio.sleep(60 * 60 * 4)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s: %(message)s"
)
loop = asyncio.get_event_loop()
task = loop.create_task(periodic())
try:
    loop.run_until_complete(task)
except asyncio.CancelledError:
    pass
