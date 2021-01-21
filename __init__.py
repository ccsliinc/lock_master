"""The Lock Manager integration."""
import asyncio
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from datetime import timedelta
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event, CoreState, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import Throttle
from openzwavemqtt.const import CommandClass

from homeassistant.components.ozw import DOMAIN as OZW_DOMAIN
from homeassistant.components.zwave import DOMAIN as ZWAVE_DOMAIN

from homeassistant.const import EVENT_STATE_CHANGED
from .sensor import CodeSensor, ATTR_SENSOR_SLOT_ENABLED, ATTR_SENSOR_SETTINGS
from .schema import SLOT_SETTINGS_SCHEMA
from .const import (
    DOMAIN,
    LOCK_DOMAIN,
    NOTIFY_DOMAIN,
    SENSOR_DOMAIN,
    ATTR_ENTITY_ID,
    CONF_ALARM_LEVEL,
    CONF_ALARM_TYPE,
    CONF_ENTITY_ID,
    CONF_LOCK_NAME,
    CONF_LOCK_NAME_SAFE,
    CONF_NOTIFY,
    CONF_NOTIFY_DOOR_LEFT_OPEN,
    CONF_NOTIFY_DOOR_OPEN,
    CONF_OPEN_DURATION,
    CONF_SENSOR_NAME,
    CONF_SLOTS,
    CONF_START, CODES_KWIKSET, CONF_NOTIFY_LOCK_GENERAL,
)

PLATFORMS = ["sensor"]

# Services
SERVICE_ADD_CODE = "add_code"
SERVICE_CLEAR_CODE = "clear_code"
SERVICE_REFRESH_CODES = "refresh_codes"
SERVICE_UPDATE_SLOT = "update_slot"
SERVICE_CLEAR_SLOT = "clear_slot"
SERVICE_SLOT_ENABLED = "slot_enabled"
SERVICE_UPDATE_SETTINGS = "update_settings"
SERVICE_RESET_LOCK = "reset_lock"

# Zwave
ZWAVE_MANAGER = "manager"
ZWAVE_SET_USERCODE = "set_usercode"
ZWAVE_CLEAR_USERCODE = "clear_usercode"
ZWAVE_INSTANCE_ID = 1
OZW_STATUS_LEVELS = ["driverAwakeNodesQueried", "driverAllNodesQueriedSomeDead", "driverAllNodesQueried"]
ZWAVE_NETWORK = "zwave_network"

ENTRY = "entry"
ENTRY_TYPE = "type"
ENTRY_ID = "entry_id"
INDEX = "index"
STATUS = "Status"
VALUE = "value"
SENSORS = "sensors"
UPDATE_LISTENER = "update_listener"
ATTR_NODE_ID = "node_id"
ATTR_USER_CODE = "usercode"
ATTR_CODE_SLOT = "code_slot"
LOCK_INFO = "lock_info"

# Lock
LOCK_MANUFACTURER = "manufacturer"
LOCK_MODEL = "model"

# Code
CODE_STATUS = "status"
CODE_USER = "user"
CODE_NOTIFY = "notify"

DEVICES_WITH_EVENTS = [CONF_ENTITY_ID, CONF_SENSOR_NAME, CONF_ALARM_TYPE]

REFRESH_CODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_domain(LOCK_DOMAIN)
})

RESET_LOCK_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_domain(LOCK_DOMAIN)
})

CLEAR_CODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): vol.All(cv.entity_domain(SENSOR_DOMAIN), vol.Match(r'^sensor\..*_code_slot_\d*$'))
})

UPDATE_CODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): vol.All(cv.entity_domain(SENSOR_DOMAIN), vol.Match(r'^sensor\..*_code_slot_\d*$')),
    vol.Required(ATTR_USER_CODE): int,
})

SLOT_ENABLED_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): vol.All(cv.entity_domain(SENSOR_DOMAIN), vol.Match(r'^sensor\..*_code_slot_\d*$')),
    vol.Required(ATTR_SENSOR_SLOT_ENABLED): bool,
})


_LOGGER = logging.getLogger(__name__)


class LockManagerCoordinator:
    """Define an object to hold Lock Manager Data"""

    def __init__(self, hass: HomeAssistant):
        """Initialize"""
        self._hass = hass
        self.updater = Updater(hass, self)
        self._event_listener = None
        self._services = []
        self._entries = {}
        self._event_watch_list = {}
        self._load()
        self._default_notifier = None
        self._door_timer = None
        self._lock_timer = None

    @property
    def automation_enabled(self) -> bool:
        """Has everything started and automation is enabled"""
        # hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, almond_hass_start)
        if self._hass.state != CoreState.running:
            # _LOGGER.warning("Automation not ready : HA has not started")
            return False

        if OZW_DOMAIN in self._hass.data:
            manager = self._hass.data[OZW_DOMAIN][ZWAVE_MANAGER]
            status = manager.get_instance(ZWAVE_INSTANCE_ID).get_status().data[STATUS]
            if status not in OZW_STATUS_LEVELS:
                _LOGGER.warning(f"Automation not ready : OZW not loaded - status:{status}")
                return False

        if ZWAVE_NETWORK in self._hass.data:
            # TODO Test zwave network
            # self._hass.data[ZWAVE_NETWORK]
            _LOGGER.warning(f"Automation not ready : ZWAVE not loaded")
            return False

        return True

    @property
    def entries(self):
        """Return the current entries"""
        return self._entries

    def add_sensor(self, code_sensor: CodeSensor, entry: ConfigEntry) -> None:
        self._entries[entry.entry_id][SENSORS][f"sensor.{code_sensor.name}"] = code_sensor

    async def _get_device(self, entity_id):
        _entity_registry = await self._hass.helpers.entity_registry.async_get_registry()
        _entity = _entity_registry.async_get(entity_id)
        _device_id = _entity.device_id
        _device_registry = await self._hass.helpers.device_registry.async_get_registry()
        _device = _device_registry.async_get(_device_id)
        return _device

    def _find_sensor(self, sensor_name: str) -> Optional[CodeSensor]:
        for k, v in self._entries.items():
            if sensor_name in v[SENSORS].keys():
                return v[SENSORS][sensor_name]
        return None

    async def _find_lock(self, lock_name: str) -> Optional[ConfigEntry]:
        for k, v in self._entries.items():
            if lock_name == v[ENTRY].data[CONF_ENTITY_ID]:
                return v[ENTRY]
        return None

    async def load_entry(self, entry: ConfigEntry) -> None:
        """Add a new entry"""
        entry.options = entry.data  # Sync data/options
        _device = await self._get_device(entry.data[ATTR_ENTITY_ID])
        self._entries[entry.entry_id] = {
            ENTRY: entry,
            UPDATE_LISTENER: entry.add_update_listener(update_listener),
            SENSORS: {},
            LOCK_INFO: {
                LOCK_MANUFACTURER: _device.manufacturer,
                LOCK_MODEL: _device.model,
            }
        }

        # Picking one of the entries notifiers as a fallback notifier
        if not self._default_notifier and CONF_NOTIFY in entry.data and entry.data[CONF_NOTIFY]:
            self._default_notifier = entry.data[CONF_NOTIFY]

        # Adding events we want to watch to the watch list
        for d in DEVICES_WITH_EVENTS:
            if entry.data[d]:
                self._event_watch_list[entry.data[d]] = {
                    ATTR_ENTITY_ID: entry.data[d],
                    ENTRY_TYPE: d,
                    ENTRY_ID: entry.entry_id
                }

        for component in PLATFORMS:
            self._hass.async_create_task(
                self._hass.config_entries.async_forward_entry_setup(entry, component)
            )

    async def unload_entry(self, entry: ConfigEntry, reload: bool = False) -> bool:
        """Remove an entry"""
        unload_ok = all(
            await asyncio.gather(
                *[
                    self._hass.config_entries.async_forward_entry_unload(entry, component)
                    for component in PLATFORMS
                ]
            )
        )

        self._entries[entry.entry_id][UPDATE_LISTENER]()
        self._entries.pop(entry.entry_id)

        # Remove sensors from watch list
        for d in DEVICES_WITH_EVENTS:
            if entry.data[d]:
                self._event_watch_list.pop(entry.data[d])

        if not reload:
            # If we have no more entries remove services and listeners
            if len(self._entries) == 0:
                await self._unload_services()
                await self._unload_event_listener()

        return unload_ok

    async def update_entry(self, entry: ConfigEntry) -> None:
        """Update an entry"""
        await self.unload_entry(entry, True)
        await self.load_entry(entry)

    async def remove_entry(self, entry: ConfigEntry) -> None:
        """Remove an entry"""

    async def state_changed(self, _: Event, args):
        # Lock state changed
        if args[ENTRY_TYPE] == CONF_ENTITY_ID:
            _LOGGER.debug("Lock State Changed", args)
            await self._lock_state_changed(_, args)
        # Door state changed
        elif args[ENTRY_TYPE] == CONF_SENSOR_NAME:
            _LOGGER.debug("Door State Changed", args)
            await self._door_state_changed(_, args)
        elif args[ENTRY_TYPE] == CONF_ALARM_TYPE:
            _LOGGER.debug("Alarm State Changed", args)
            await self._door_state_changed(_, args)

    async def _lock_state_changed(self, _: Event, args):
        """The lock state changed"""
        _entry: ConfigEntry = self._entries[args[ENTRY_ID]][ENTRY]
        _notifier = _entry.data[CONF_NOTIFY]
        _should_alert = _entry.data[CONF_NOTIFY_DOOR_OPEN]

        _LOGGER.debug(f"Lock has been {_.data['new_state'].state}")

        @callback
        async def _lock_changed(_now) -> None:
            if _notifier and _should_alert:
                _alert = f"{_entry.data[CONF_LOCK_NAME]} : Lock state changed and change event did not fire.."
                _LOGGER.error(_alert)
                await self.notify(_alert, _notifier)
            return

        self._lock_timer = async_call_later(self._hass, 30, _lock_changed)

    async def _alarm_level_changed(self,  _: Event, args):
        _entry: ConfigEntry = self._entries[args[ENTRY_ID]][ENTRY]
        _notifier = _entry.data[CONF_NOTIFY]
        _name = _entry.data[CONF_LOCK_NAME]
        _safe_name = _entry.data[CONF_LOCK_NAME_SAFE]
        _lock_info = self._entries[args[ENTRY_ID]][LOCK_INFO]
        _lock_const = {}

        if "kwikset" in _lock_info[LOCK_MANUFACTURER].lower():
            _lock_const = CODES_KWIKSET
        elif "schlage" in _lock_info[LOCK_MANUFACTURER].lower():
            _lock_const = CODES_KWIKSET

        if _lock_const:
            _type = self._hass.states.get(_entry.data[CONF_ALARM_TYPE])
            _level = self._hass.states.get(_entry.data[CONF_ALARM_LEVEL])

            _status = _lock_const[CODE_STATUS][_type]

            if _status in _lock_const[CODE_STATUS]:
                # Alarm was triggered by a user
                _user = _level
                _code_sensor = self._find_sensor(f"sensor.{_safe_name}_code_slot_{_user}")
                if _code_sensor:
                    await _code_sensor.increment_counter()
                    if _code_sensor.should_alert and _notifier:
                        await self.notify(f"{_status} : {_code_sensor.user_name}.", _notifier)

                else:
                    _LOGGER.error("Lock state changed via unknown user")

            else:
                _should_alert = _entry.data[CONF_NOTIFY_LOCK_GENERAL]
                if _should_alert and _type in _lock_const[CODE_NOTIFY] and _notifier:
                    await self.notify(f"{_name} status changed to {_status}.", _notifier)

            if self._lock_timer:
                self._lock_timer()
                self._lock_timer = None
        else:
            _LOGGER.error("Could not match lock manufacturer")

    async def _door_state_changed(self, _: Event, args):
        """The lock door changed"""
        _entry: ConfigEntry = self._entries[args[ENTRY_ID]][ENTRY]
        _should_alert = _entry.data[CONF_NOTIFY_DOOR_OPEN]
        _notifier = _entry.data[CONF_NOTIFY]
        _name = _entry.data[CONF_LOCK_NAME]

        @callback
        async def _door_remains_open(_now) -> None:
            await self.notify(f"{_name} has been left open.", _notifier)
            self._door_timer = async_call_later(self._hass, _entry.data[CONF_OPEN_DURATION], _door_remains_open)
            return

        if _.data['new_state'].state == 'on' and _should_alert and _notifier:
            await self.notify(f"{_name} has been opened.", _notifier)

        if _entry.data[CONF_NOTIFY_DOOR_LEFT_OPEN] and _.data['new_state'].state == 'on':
            self._door_timer = async_call_later(self._hass, _entry.data[CONF_OPEN_DURATION], _door_remains_open)
        else:
            if self._door_timer:
                self._door_timer()
                self._door_timer = None

    def generate_lovelace(self):
        return

    async def reset_lock(self, entity: str):
        _LOGGER.debug("Resetting Lock")
        entry = await self._find_lock(entity)
        if entry:
            sensors = self._entries[entry.entry_id][SENSORS]
            for s in sensors.values():
                await s.reset_slot()
        return

    async def zwave_refresh_codes(self, entity: str):
        if not self.automation_enabled:
            # Bail if network is not ready
            return

        _LOGGER.debug("Zwave Refresh Codes call started.")
        if OZW_DOMAIN in self._hass.data:
            try:
                state = self._hass.states.get(entity)
                node_id = state.attributes[ATTR_NODE_ID]
                manager = self._hass.data[OZW_DOMAIN][ZWAVE_MANAGER]
                lock_values = manager.get_instance(ZWAVE_INSTANCE_ID).get_node(node_id).values()
                for value in lock_values:
                    if (
                            value.command_class == CommandClass.USER_CODE
                            and value.index == 255
                    ):
                        _LOGGER.debug(
                            "DEBUG: Index found valueIDKey: %s", int(value.value_id_key)
                        )
                        value.send_value(True)
                        value.send_value(False)
            except Exception:
                _LOGGER.error("Error extracting node_id")

        _LOGGER.debug("Zwave Refresh Codes call completed.")

    async def zwave_update_code(self, service_data: dict, clear: bool = False):
        if not self.automation_enabled:
            # Bail if network is not ready
            return

        _LOGGER.debug(f"Zwave Code update call started.")

        if OZW_DOMAIN in self._hass.data:
            domain = OZW_DOMAIN
        elif ZWAVE_NETWORK in self._hass.data:
            domain = ZWAVE_DOMAIN
        else:
            _LOGGER.info("Cannot find the zwave domain")
            return

        if clear:
            action = ZWAVE_CLEAR_USERCODE
            service_data.pop(ATTR_USER_CODE)
        else:
            action = ZWAVE_SET_USERCODE

        try:
            await self._hass.services.async_call(domain, action, service_data)
        except Exception as err:
            _LOGGER.error(
                f"Error calling {domain}.{action} service call: {str(err)}"
            )
            pass

        _LOGGER.debug(f"Zwave Code {domain}.{action} call completed.")

    async def entity_update_code(self, entity: CodeSensor, clear: bool = False):
        _LOGGER.debug(f"Entity Code update call started.")
        service_data = {
            ATTR_ENTITY_ID: entity.parent,
            ATTR_CODE_SLOT: entity.slot,
            ATTR_USER_CODE: entity.code
        }
        await self.zwave_update_code(service_data, clear)
        _LOGGER.debug(f"Entity Code update call finished.")

    async def notify(self, message: str, service: str = None, important: bool = False):
        """Used for notifications"""
        if self.automation_enabled:
            _LOGGER.info(message)

            if not service:
                service = self._default_notifier

            if service:
                await self._hass.services.async_call(NOTIFY_DOMAIN, service, {"message": message})

            if important:
                await self._hass.services.async_call(NOTIFY_DOMAIN, "persistent_notification", {"message": message})

    def _load(self):

        # region Event Listener
        async def event_listener(_: Event) -> None:
            if self.automation_enabled:
                if _.data[ATTR_ENTITY_ID] in self._event_watch_list.keys():
                    _entry = self._event_watch_list[_.data[ATTR_ENTITY_ID]]
                    await self.state_changed(_, _entry)

        self._event_listener = self._hass.bus.async_listen(EVENT_STATE_CHANGED, event_listener)
        # endregion

        # region Reset Lock
        async def _reset_lock(service):
            """Reset Lock - Service"""
            _LOGGER.debug("Resetting Lock")
            lock = service.data[ATTR_ENTITY_ID]
            await self.reset_lock(lock)

        self._services.append(SERVICE_RESET_LOCK)
        self._hass.services.async_register(DOMAIN, SERVICE_RESET_LOCK, _reset_lock, RESET_LOCK_SCHEMA)
        # endregion

        # region Refresh Lock Codes
        async def _refresh_lock_codes(service):
            """Refresh Lock Codes - Service"""
            _LOGGER.debug("Refreshing Lock Codes")
            lock = service.data[ATTR_ENTITY_ID]
            await self.zwave_refresh_codes(lock)

        self._services.append(SERVICE_REFRESH_CODES)
        self._hass.services.async_register(DOMAIN, SERVICE_REFRESH_CODES, _refresh_lock_codes, REFRESH_CODE_SCHEMA)
        # endregion

        # region Update Slot
        async def _update_slot(service):
            """Update Code Sensor - Service"""
            _LOGGER.debug("Updating the CodeSensor")
            _sensor_name = service.data[ATTR_ENTITY_ID]
            _code = service.data[ATTR_USER_CODE]
            _entity: CodeSensor = self._find_sensor(_sensor_name)

            if _entity:
                await _entity.update_code(_code)

        self._services.append(SERVICE_UPDATE_SLOT)
        self._hass.services.async_register(DOMAIN, SERVICE_UPDATE_SLOT, _update_slot, UPDATE_CODE_SCHEMA)

        # endregion

        # region Clear Slot
        async def _clear_slot(service):
            """Reset Code Sensor - Service"""
            _LOGGER.debug("Clearing the CodeSensor")
            _sensor_name = service.data[ATTR_ENTITY_ID]
            _entity: CodeSensor = self._find_sensor(_sensor_name)

            if _entity:
                await _entity.reset_slot()

        self._services.append(SERVICE_CLEAR_SLOT)
        self._hass.services.async_register(DOMAIN, SERVICE_CLEAR_SLOT, _clear_slot, CLEAR_CODE_SCHEMA)
        # endregion

        # region Enable/Disable Slot
        async def _slot_enabled(service):
            """Enable or Disable the slot"""
            _LOGGER.debug("Enable/Disable code slot")
            _sensor_name = service.data[ATTR_ENTITY_ID]
            _state = service.data[ATTR_SENSOR_SLOT_ENABLED]

            _entity: CodeSensor = self._find_sensor(_sensor_name)
            if _entity:
                if _state:
                    await _entity.enable()
                else:
                    await _entity.disable()

        self._services.append(SERVICE_SLOT_ENABLED)
        self._hass.services.async_register(DOMAIN, SERVICE_SLOT_ENABLED, _slot_enabled, SLOT_ENABLED_SCHEMA)
        # endregion

        # region Update slot settings
        async def _slot_settings(service):
            """Update the settings of the slot"""
            _LOGGER.debug("Updating code slot settings")
            _sensor_name = service.data[ATTR_ENTITY_ID]
            _settings = service.data[ATTR_SENSOR_SETTINGS]

            _entity: CodeSensor = self._find_sensor(_sensor_name)

            if _entity:
                await _entity.update_settings(_settings)

        self._services.append(SERVICE_UPDATE_SETTINGS)
        self._hass.services.async_register(DOMAIN, SERVICE_UPDATE_SETTINGS, _slot_settings, SLOT_SETTINGS_SCHEMA)
        # endregion

    async def _unload_services(self):
        for s in self._services:
            self._hass.services.remove(s)

    async def _unload_event_listener(self):
        self._event_listener.remove()


class Updater:
    """The class for handling the data retrieval."""

    def __init__(self, hass, coordinator: LockManagerCoordinator):
        """Initialize the data object."""
        self._hass = hass
        self._errors = 0
        self._enabled = False
        self.update = Throttle(timedelta(seconds=30))(self.update)
        self._coordinator = coordinator

    @property
    def enabled(self):
        return self._enabled

    def enable(self):
        """Enable Data Updater"""
        self._enabled = True

    def disable(self):
        """Disable Data Updater"""
        self._enabled = False

    async def _get_latest_zwave_data(self):
        """Connect and retrieve zwave information"""

        if not self._coordinator.automation_enabled or not self.enabled:
            # Bail if network is not ready
            return

        _LOGGER.debug("Starting to fetch codes from zwave")
        entries = self._coordinator.entries

        for entry in entries:
            domain = None
            _entry: ConfigEntry = entries[entry][ENTRY]
            _sensors = entries[entry][SENSORS]
            try:
                state = self._hass.states.get(_entry.data[ATTR_ENTITY_ID])
                node_id = state.attributes[ATTR_NODE_ID]
                lock_values = None
                lower_index = _entry.data[CONF_START]
                upper_index = _entry.data[CONF_SLOTS] + lower_index - 1

                if OZW_DOMAIN in self._hass.data:

                    domain = OZW_DOMAIN
                    manager = self._hass.data[OZW_DOMAIN][ZWAVE_MANAGER]
                    lock_values = (
                        manager
                        .get_instance(ZWAVE_INSTANCE_ID)
                        .get_node(node_id)
                        .get_command_class(CommandClass.USER_CODE)
                        .values()
                    )
                elif ZWAVE_NETWORK in self._hass.data:
                    domain = ZWAVE_NETWORK
                    network = self._hass.data[ZWAVE_NETWORK]
                    lock_values = (
                        network
                        .nodes[node_id]
                        .get_values(class_id=CommandClass.USER_CODE)
                        .values()
                    )
                else:
                    _LOGGER.info(f"No available zwave managers")

                if lock_values:
                    for value in lock_values:
                        # Skip unwanted values from ozw
                        if domain == OZW_DOMAIN and value.command_class != CommandClass.USER_CODE:
                            continue

                        # Skip unused indexes
                        if not (lower_index <= value.index <= upper_index):
                            continue

                        # TODO check zwave platform
                        # Normalize data structure
                        data = {INDEX: value.index, VALUE: ""}
                        if domain == OZW_DOMAIN:
                            data[VALUE] = value.value
                        else:
                            data[VALUE] = value.data

                        sensor_name = f"sensor.{_entry.data[CONF_LOCK_NAME_SAFE]}_code_slot_{data[INDEX]}"

                        _LOGGER.debug(f"{sensor_name} value: {str(data[VALUE])}")

                        if sensor_name in _sensors:
                            entity: CodeSensor = _sensors[sensor_name]
                            await entity.zwave_code_check(data[VALUE].replace("\x00", ""))

            except Exception:
                _LOGGER.error(f"Error getting codes from {domain} manager", exc_info=True)
                self._errors += 1
                if self._errors > 10:
                    await self._coordinator.notify(
                        "Data updater has been disabled due to too many errors.  Check Home Assistant logs.",
                        important=True
                    )

        _LOGGER.debug("Finishing to fetch codes from zwave")

    async def update(self):
        await self._get_latest_zwave_data()


async def async_setup(hass: HomeAssistant, config: dict):
    """ Disallow configuration via YAML """
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Lock Manager from a config entry."""
    if DOMAIN not in hass.data:
        hass.data.setdefault(DOMAIN, LockManagerCoordinator(hass))

    coordinator: LockManagerCoordinator = hass.data[DOMAIN]
    await coordinator.load_entry(entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    coordinator: LockManagerCoordinator = hass.data[DOMAIN]
    unload_ok = await coordinator.unload_entry(entry)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove an entry"""
    coordinator: LockManagerCoordinator = hass.data[DOMAIN]
    await coordinator.remove_entry(entry)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update listener."""
    entry.data = entry.options
    coordinator: LockManagerCoordinator = hass.data[DOMAIN]
    await coordinator.update_entry(entry)
