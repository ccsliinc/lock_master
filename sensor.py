""" Sensor for Lock Manager """

import logging
import datetime

from typing import Any, Dict, Optional
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.core import HomeAssistant, callback
from .const import (
    DOMAIN,
    CONF_SLOTS, CONF_START, CONF_LOCK_NAME_SAFE, CONF_NOTIFY, CONF_ENTITY_ID,

    ATTR_BEGIN_DATE, ATTR_END_DATE, ATTR_START_TIME, ATTR_INCLUSIVE,
    ATTR_LIMIT, ATTR_END_TIME, ATTR_ENABLED, ATTR_DAYS,
    ATTR_SENSOR_SETTINGS, ATTR_SENSOR_SLOT_ENABLED, ATTR_SEN_SET_BY_ACCESS_COUNT, ATTR_SENSOR_COUNT,
    ATTR_SEN_SET_BY_DATE_RANGE, ATTR_SEN_SET_BY_DOW, ATTR_SEN_SET_LOCK_CODE, ATTR_SEN_SET_NOTIFICATION,
    ATTR_SEN_SET_USER_NAME,
)

from .schema import CODE_SENSOR_SCHEMA, CODE_SENSOR_SETTINGS_SCHEMA

# SETTABLE PARAMS
PARAM_OUT_OF_SYNC_COUNT = 5
ICON = "mdi:lock-smart"

# STATUSES
STATUS_UNKNOWN = "Unknown"
STATUS_GRANTED = "Access Granted"
STATUS_NO_SETTINGS = "Settings are not present for this lock"
STATUS_NOT_TODAY = "This user does not have permission today."
STATUS_NOT_TIME_PERIOD = "This user does not have permission during this time."
STATUS_NOT_DATE = "This user does not have permission on this date."
STATUS_COUNT_EXCEEDED = "This user has reached the amount of allowed logins."
STATUS_DISABLED = "This user has been disabled."

# STATES
STATE_ENABLED = "Enabled"
STATE_DISABLE = "Disabled"
STATE_DIRTY = "Dirty"
STATE_UNKNOWN = "Unknown"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    _slots = entry.data[CONF_SLOTS]
    _start_from = entry.data[CONF_START]
    _entities = []

    for x in range(_start_from, _start_from + _slots):
        _entities.append(CodeSensor(hass, entry, x))

    async_add_entities(_entities, True)


class CodeSensor(RestoreEntity):
    """Represents a CodeSensor"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, slot: int):

        self._attrs = CODE_SENSOR_SCHEMA({})

        self._hass = hass
        self._entry = entry
        self._slot = slot
        self._name = f"{entry.data[CONF_LOCK_NAME_SAFE]}_code_slot_{slot}"
        self._status = STATUS_UNKNOWN
        self._code = None

        self._state = STATE_DISABLE
        self._previous_state = STATE_DISABLE
        self._error_count = 0
        self._zwave_code = None

        self._notify = entry.data[CONF_NOTIFY]

        # Helper Functions
        self._coordinator = hass.data[DOMAIN]
        self._updater = self._coordinator.updater

        self._coordinator.add_sensor(self, entry)

    @property
    def parent(self) -> str:
        """Return parent of code slot"""
        return self._entry.data[CONF_ENTITY_ID]

    @property
    def slot(self) -> int:
        """Return current slot"""
        return self._slot

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry.entry_id}_code_slot_{self._slot}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self) -> Optional[str]:
        """Return the icon."""
        return ICON

    @property
    def state(self) -> StateType:
        """Return the state."""
        return self._state

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        return self._attrs

    @property
    def status(self) -> Optional[str]:
        """Returns the current status"""
        return self._status

    @property
    def code(self) -> Optional[int]:
        """Returns the current code"""
        return self._code

    @property
    def should_alert(self) -> bool:
        """Should we alert for this user"""
        try:
            return self._attrs[ATTR_SENSOR_SETTINGS][ATTR_SEN_SET_NOTIFICATION]
        finally:
            return False

    @property
    def user_name(self) -> str:
        """User's Name"""
        try:
            return self._attrs[ATTR_SENSOR_SETTINGS][ATTR_SEN_SET_USER_NAME]
        finally:
            return ""

    async def update_settings(self, settings):
        _attrs = CODE_SENSOR_SCHEMA(self._attrs)
        _attrs[ATTR_SENSOR_SETTINGS] = CODE_SENSOR_SETTINGS_SCHEMA(settings)
        self._attrs = _attrs
        await self._check_current_status()

    async def enable(self):
        if ATTR_SENSOR_SETTINGS in self._attrs:
            self._attrs[ATTR_SENSOR_SLOT_ENABLED] = True
            await self._check_current_status()

    async def disable(self):
        self._attrs[ATTR_SENSOR_SLOT_ENABLED] = False
        await self._check_current_status()

    async def update_code(self, code: int):
        self._attrs = CODE_SENSOR_SCHEMA({**self._attrs, **{ATTR_SEN_SET_LOCK_CODE: code}})
        await self._check_current_status()

    async def reset_slot(self):
        self._attrs = CODE_SENSOR_SCHEMA({})
        await self._check_current_status()

    async def reset_code_count(self):
        self._attrs[ATTR_SENSOR_COUNT] = 0
        await self._check_current_status()

    async def increment_counter(self):
        self._attrs[ATTR_SENSOR_COUNT] += 1
        await self._check_current_status()

    async def zwave_code_check(self, code: str):
        """This is called when the DataUpdater grabs the code from ZWave Manager"""

        _code = int(code) if code.isnumeric() else None

        if self._error_count >= PARAM_OUT_OF_SYNC_COUNT:
            await self._coordinator.notify(
                f"Slot and Lock are out of sync. {self._name} Check Home Assistant logs. We are not going to try and "
                f"update this slot any further.  Look into the issue and reboot home assistant to reset the counter. ",
                self._notify, True)
        else:
            if ATTR_SENSOR_SETTINGS in self._attrs:
                self._zwave_code = _code

                if code != self.code and self.state == STATE_ENABLED:
                    _LOGGER.debug('Slot and Lock out of sync, slot is enabled. Trying to remedy.')
                    self._state = STATE_DIRTY
                    await self._check_current_status()
                    self._error_count += 1
                elif self.state == STATE_DISABLE and code:
                    _LOGGER.debug('Slot and Lock out of sync, slot is disabled. Trying to remedy.')
                    self._state = STATE_DIRTY
                    await self._check_current_status()
                    self._error_count += 1
                else:
                    self._error_count = 0

    async def _set_state(self, state: str):
        """Set the current state and sync's lock"""
        # If the current state does not match the new state
        if state != self._state:
            self._previous_state = self._state
            self._state = state

            if state == STATE_ENABLED:
                await self._coordinator.entity_update_code(self, False)
            elif state == STATE_DISABLE:
                await self._coordinator.entity_update_code(self, True)
            else:
                self._state = STATE_UNKNOWN
                _LOGGER.error("Invalid state set")

    async def _check_current_status(self):
        """Determines if this slot should be enabled/disabled"""

        if ATTR_SENSOR_SETTINGS in self._attrs:
            _settings = self._attrs[ATTR_SENSOR_SETTINGS]

            if not self._attrs[ATTR_SENSOR_SLOT_ENABLED]:
                await self._set_state(STATE_DISABLE)
                self._status = STATUS_DISABLED
                return

            # Logic for Access Count
            if ATTR_SEN_SET_BY_ACCESS_COUNT in _settings:
                _by_count = _settings[ATTR_SEN_SET_BY_ACCESS_COUNT]
                if _by_count[ATTR_ENABLED] and _by_count[ATTR_LIMIT] >= self._attrs[ATTR_SENSOR_COUNT]:
                    await self._set_state(STATE_DISABLE)
                    self._status = STATUS_COUNT_EXCEEDED
                    return

            # Logic for Date Range checks
            if ATTR_SEN_SET_BY_DATE_RANGE in _settings and _settings[ATTR_SEN_SET_BY_DATE_RANGE][ATTR_ENABLED]:
                _by_date_range = _settings[ATTR_SEN_SET_BY_DATE_RANGE]
                now = datetime.datetime.now().date()
                begin_date = datetime.datetime.strptime(_by_date_range[ATTR_BEGIN_DATE], '%Y-%m-%d').date()
                end_date = datetime.datetime.strptime(_by_date_range[ATTR_END_DATE], '%Y-%m-%d').date()
                if not (begin_date <= now <= end_date):
                    await self._set_state(STATE_DISABLE)
                    self._status = STATUS_NOT_DATE
                    return

            # Logic for Day of the Week checks
            if ATTR_SEN_SET_BY_DOW in _settings and _settings[ATTR_SEN_SET_BY_DOW][ATTR_ENABLED]:
                _by_dow = _settings[ATTR_SEN_SET_BY_DOW]
                now = datetime.datetime.now().time()
                today_name = datetime.datetime.now().strftime("%A").lower()

                if today_name in _by_dow[ATTR_DAYS]:
                    _dow_attr = _by_dow[ATTR_DAYS][today_name]
                    start_time = datetime.datetime.strptime(_dow_attr[ATTR_START_TIME], '%H:%M:%S').time()
                    end_time = datetime.datetime.strptime(_dow_attr[ATTR_END_TIME], '%H:%M:%S').time()
                    if _dow_attr[ATTR_INCLUSIVE]:
                        if not (start_time <= now <= end_time):
                            await self._set_state(STATE_DISABLE)
                            self._status = STATUS_NOT_TIME_PERIOD
                            return

                    else:
                        if start_time <= now <= end_time:
                            await self._set_state(STATE_DISABLE)
                            self._status = STATUS_NOT_TIME_PERIOD
                            return
                else:
                    await self._set_state(STATE_DISABLE)
                    self._status = STATUS_NOT_TODAY
                    return
        else:
            self._status = STATUS_NO_SETTINGS
            await self._set_state(STATE_DISABLE)
            return

        # If we made it this far code slot is enabled
        await self._set_state(STATE_ENABLED)
        self._status = STATUS_GRANTED

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added"""
        await super().async_added_to_hass()
        _restored_state = await self.async_get_last_state()
        if not _restored_state:
            _LOGGER.error("Could not restore previous state.")
            return
        self._state = _restored_state.state
        self._attrs = CODE_SENSOR_SCHEMA({**self._attrs, **_restored_state.attributes})
        await self._check_current_status()

    async def async_update(self):
        """Get the latest data and updates the state."""
        await self._updater.update()
        await self._check_current_status()

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)
