import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_BEGIN_DATE,
    ATTR_DAYS,
    ATTR_DAYS_OF_WEEK,
    ATTR_ENABLED,
    ATTR_END_DATE,
    ATTR_END_TIME,
    ATTR_ENTITY_ID,
    ATTR_INCLUSIVE,
    ATTR_LIMIT,
    ATTR_SEN_SET_BY_ACCESS_COUNT,
    ATTR_SEN_SET_BY_DATE_RANGE,
    ATTR_SEN_SET_BY_DOW,
    ATTR_SEN_SET_LOCK_CODE,
    ATTR_SEN_SET_NOTIFICATION,
    ATTR_SEN_SET_USER_NAME,
    ATTR_SENSOR_COUNT,
    ATTR_SENSOR_FRIENDLY_NAME,
    ATTR_SENSOR_ICON,
    ATTR_SENSOR_SETTINGS,
    ATTR_SENSOR_SLOT_ENABLED,
    ATTR_START_TIME,
)

ACCESS_COUNT_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENABLED): bool,
    vol.Required(ATTR_LIMIT): int,
}, extra=vol.REMOVE_EXTRA)

DATE_RANGE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENABLED): bool,
    vol.Required(ATTR_BEGIN_DATE): vol.All(cv.date, vol.Coerce(str)),
    vol.Required(ATTR_END_DATE): vol.All(cv.date, vol.Coerce(str)),
}, extra=vol.REMOVE_EXTRA)

TIME_SCHEMA = vol.Schema({
    vol.Required(ATTR_START_TIME): vol.All(cv.time, vol.Coerce(str)),
    vol.Required(ATTR_END_TIME): vol.All(cv.time, vol.Coerce(str)),
    vol.Required(ATTR_INCLUSIVE): bool
}, extra=vol.REMOVE_EXTRA)

DAY_SCHEMA = vol.Schema({
    vol.In(ATTR_DAYS_OF_WEEK): vol.Schema(TIME_SCHEMA),
}, extra=vol.REMOVE_EXTRA)

DOW_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENABLED): bool,
    vol.Required(ATTR_DAYS): vol.Schema(DAY_SCHEMA),
}, extra=vol.REMOVE_EXTRA)

CODE_SENSOR_SETTINGS_SCHEMA = vol.Schema({
    vol.Required(ATTR_SEN_SET_LOCK_CODE): int,
    vol.Required(ATTR_SEN_SET_USER_NAME): str,
    vol.Optional(ATTR_SEN_SET_BY_ACCESS_COUNT): vol.Schema(ACCESS_COUNT_SCHEMA),
    vol.Optional(ATTR_SEN_SET_BY_DATE_RANGE): vol.Schema(DATE_RANGE_SCHEMA),
    vol.Optional(ATTR_SEN_SET_BY_DOW): vol.Schema(DOW_SCHEMA),
    vol.Required(ATTR_SEN_SET_NOTIFICATION, default=False): bool
}, extra=vol.REMOVE_EXTRA)

CODE_SENSOR_SCHEMA = vol.Schema({
    vol.Required(ATTR_SENSOR_SLOT_ENABLED, default=False): bool,
    vol.Required(ATTR_SENSOR_COUNT, default=0): int,
    vol.Optional(ATTR_SENSOR_ICON): str,
    vol.Optional(ATTR_SENSOR_FRIENDLY_NAME): str,
    vol.Optional(ATTR_SENSOR_SETTINGS): vol.Schema(CODE_SENSOR_SETTINGS_SCHEMA)
}, extra=vol.REMOVE_EXTRA)

SLOT_SETTINGS_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): vol.All(cv.entity_id, vol.Match(r'^sensor\..*_code_slot_\d*$')),
    vol.Required(ATTR_SENSOR_SETTINGS): vol.Schema(CODE_SENSOR_SETTINGS_SCHEMA)
})
