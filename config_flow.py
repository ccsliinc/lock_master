"""Config flow for Lock Manager integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import DOMAIN as BINARY_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSORS_DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import callback

from .const import (
    DOMAIN,
    LOCK_DOMAIN,
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
    CONF_START, CONF_NOTIFY_LOCK_GENERAL,
)

# DEFAULT Values
DEFAULT_START = 1
DEFAULT_CODE_SLOTS = 10
DEFAULT_SENSOR = "binary_sensor.fake"

_LOGGER = logging.getLogger(__name__)


async def _setup(obj):
    entities = obj.hass.states.async_entity_ids(SENSORS_DOMAIN)

    locks = obj.hass.states.async_entity_ids(LOCK_DOMAIN)
    notifiers = list(obj.hass.services.async_services().get(NOTIFY_DOMAIN).keys())
    door_sensors = obj.hass.states.async_entity_ids(BINARY_DOMAIN)
    door_sensors.append(DEFAULT_SENSOR)

    alarm_types = [
        entity for entity in entities if entity.find("alarm_type") != -1 or entity.find("access_control") != -1
    ]

    alarm_levels = [
        entity for entity in entities if entity.find("alarm_level") != -1 or entity.find("alarm_level") != -1
    ]

    # Create schema with any options already present
    merged_data = {**{
        CONF_ENTITY_ID: None,
        CONF_SLOTS: DEFAULT_CODE_SLOTS,
        CONF_START: DEFAULT_START,
        CONF_LOCK_NAME: None,
        CONF_SENSOR_NAME: DEFAULT_SENSOR,
        CONF_ALARM_LEVEL: None,
        CONF_ALARM_TYPE: None,
        CONF_NOTIFY: None,
        CONF_NOTIFY_DOOR_OPEN: None,
        CONF_NOTIFY_DOOR_LEFT_OPEN: None,
        CONF_NOTIFY_LOCK_GENERAL: None,
        CONF_OPEN_DURATION: 300,
    }, **obj.data}

    obj._schema = vol.Schema({
        vol.Required(CONF_ENTITY_ID, default=merged_data[CONF_ENTITY_ID]): vol.In(locks),
        vol.Required(CONF_SLOTS, default=merged_data[CONF_SLOTS]): vol.Coerce(int),
        vol.Required(CONF_START, default=merged_data[CONF_START]): vol.Coerce(int),
        vol.Required(CONF_LOCK_NAME, default=merged_data[CONF_LOCK_NAME]): str,
        # vol.Optional(CONF_LOCK_NAME_SAFE): str, Hiding this so it doesn't show on config page
        vol.Optional(CONF_SENSOR_NAME, default=merged_data[CONF_SENSOR_NAME]): vol.In(door_sensors),
        vol.Optional(CONF_ALARM_LEVEL, default=merged_data[CONF_ALARM_LEVEL]): vol.In(alarm_levels),
        vol.Optional(CONF_ALARM_TYPE, default=merged_data[CONF_ALARM_TYPE]): vol.In(alarm_types),
        vol.Optional(CONF_NOTIFY, default=merged_data[CONF_NOTIFY]): vol.In(notifiers),
        vol.Optional(CONF_NOTIFY_DOOR_OPEN, default=merged_data[CONF_NOTIFY_DOOR_OPEN]): bool,
        vol.Optional(CONF_NOTIFY_DOOR_LEFT_OPEN, default=merged_data[CONF_NOTIFY_DOOR_OPEN]): bool,
        vol.Optional(CONF_NOTIFY_LOCK_GENERAL, default=merged_data[CONF_NOTIFY_LOCK_GENERAL]): bool,
        vol.Optional(CONF_OPEN_DURATION, default=merged_data[CONF_OPEN_DURATION]): vol.Coerce(int),
    }, extra=vol.REMOVE_EXTRA)


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lock Manager."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    _LOGGER.debug("Config Flow")

    def __init__(self):
        """Initialize."""
        self.data = {}
        self._locks = None
        self._doors = None
        self._alarm_type = None
        self._alarm_level = None
        self._notifiers = None
        self._schema = None
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        if user_input is not None:
            self.data.update(user_input)
            user_input[CONF_LOCK_NAME_SAFE] = user_input[CONF_LOCK_NAME].lower().replace(" ", "_")
            self.data.update({**self.data, **user_input})
            return self.async_create_entry(title=self.data[CONF_LOCK_NAME], data=self.data)

        await _setup(self)
        return self.async_show_form(step_id="user", data_schema=self._schema, errors=self._errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow for this handler."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for the Lock Manager integration."""

    _LOGGER.debug("Options Flow")

    def __init__(self, config_entry):
        """Initialize."""
        self.config = config_entry
        self.data = dict(config_entry.options)
        self._locks = None
        self._doors = None
        self._alarm_type = None
        self._alarm_level = None
        self._notifiers = None
        self._schema = None
        self._errors = {}

    async def async_step_init(self, user_input=None):
        """Manage basic options."""

        if user_input is not None:
            user_input[CONF_LOCK_NAME_SAFE] = user_input[CONF_LOCK_NAME].lower().replace(" ", "_")
            self.data.update({**self.data, **user_input})
            return self.async_create_entry(title=self.data[CONF_LOCK_NAME], data=self.data)

        await _setup(self)
        return self.async_show_form(step_id="init", data_schema=self._schema, errors=self._errors)

# TODO Cant get translations to work
