"""Constants for the Hello World integration."""
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN

DOMAIN = "lock_manager"
VERSION = "0.0.46"
ISSUE_URL = "https://github.com/FutureTense/lock-manager"
ENABLED = "enabled"

# SENSOR
ATTR_SENSOR_SLOT_ENABLED = "slot_enabled"
ATTR_SENSOR_COUNT = "count"
ATTR_SENSOR_ICON = "icon"
ATTR_SENSOR_FRIENDLY_NAME = "friendly_name"
ATTR_SENSOR_SETTINGS = "settings"

ATTR_SEN_SET_LOCK_CODE = "lock_code"
ATTR_SEN_SET_USER_NAME = "user_name"
ATTR_SEN_SET_BY_ACCESS_COUNT = "access_count"
ATTR_SEN_SET_BY_DATE_RANGE = "date_range"
ATTR_SEN_SET_BY_DOW = "day_of_week"
ATTR_SEN_SET_NOTIFICATION = "notifications"

# Attributes
ATTR_ENTITY_ID = "entity_id"
ATTR_LIMIT = "limit"
ATTR_ENABLED = "enabled"
ATTR_INCLUSIVE = "inclusive"
ATTR_DAY_OF_WEEK = "dow"
ATTR_DAYS_OF_WEEK = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
ATTR_DAYS = "days"
ATTR_BEGIN_DATE = "begin_date"
ATTR_END_DATE = "end_date"
ATTR_START_TIME = "begin_time"
ATTR_END_TIME = "end_time"


# Configuration Properties
CONF_ALARM_LEVEL = "alarm_level"
CONF_ALARM_TYPE = "alarm_type"
CONF_ENTITY_ID = "entity_id"
CONF_LOCK_NAME = "lockname"
CONF_LOCK_NAME_SAFE = "lockname_safe"
CONF_SENSOR_NAME = "sensorname"
CONF_SLOTS = "slots"
CONF_START = "start_from"
CONF_NOTIFY = "notify"
CONF_NOTIFY_DOOR_OPEN = "notify_door_opened"
CONF_NOTIFY_DOOR_LEFT_OPEN = "notify_left_open"
CONF_NOTIFY_LOCK_GENERAL = "notify_lock_general"
CONF_OPEN_DURATION = "duration"


# LOCK VALUES
CODES_KWIKSET = {
    "status": {
        9: 'Lock Jammed',
        16: 'Keypad Unlock',
        17: 'Keypad Lock Jammed',
        18: 'Keypad Lock',
        19: 'Keypad Unlock',
        21: 'Manual Lock',
        22: 'Manual Unlock',
        23: 'RF Lock Jammed',
        24: 'RF Lock',
        25: 'RF Unlock',
        26: 'Auto Lock Jammed',
        27: 'Auto Lock',
        32: 'All Codes Deleted',
        33: 'Code Deleted',
        112: 'Code Changed',
        113: 'Duplicate Code',
        161: 'Bad Code Entered',
        162: 'Lock Code Attempt Outside of Schedule',
        167: 'Battery Low',
        168: 'Battery Critical',
        169: 'Battery Too Low To Operate Lock',
        0: 'No Status Reported',
    },
    "user": [
        18,
        19
    ],
    "notify": [
        9,
        17,
        21,
        22,
        24,
        25,
        167
    ]
}

CODES_SCHLAGE = {
    "status": {
        1: 'Manual Lock',
        2: 'Manual Unlock',
        3: 'RF Lock',
        4: 'RF Unlock',
        5: 'Keypad Lock',
        6: 'Keypad Unlock',
        7: 'Manual not fully locked',
        8: 'RF not fully locked',
        9: 'Auto Lock locked',
        10: 'Auto Lock not fully locked',
        11: 'Lock Jammed',
        12: 'All User Codes Deleted',
        13: 'Single Code Deleted',
        14: 'New User Code Added',
        15: 'Duplicate Code',
        16: 'Keypad temporary disabled',
        17: 'Keypad busy',
        18: 'New Program Code Entered',
        999: 'Schlage',
    },
    "user": [
        5,
        6
    ],
    "notify": [
        1,
        2,
        7,
        3,
        4,
        11
    ]
}
