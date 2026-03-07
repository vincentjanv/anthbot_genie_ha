"""Constants for the Anthbot Genie integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "anthbot_genie"

CONF_API_HOST = "api_host"
CONF_BEARER_TOKEN = "bearer_token"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_AREA_CODE = "area_code"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_NAME = "Anthbot Genie 600"
DEFAULT_API_HOST = "api.anthbot.com"
DEFAULT_AREA_CODE = "32"

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_SCAN_INTERVAL_DELTA = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Service names and attributes.
SERVICE_START_FULL_MOW = "start_full_mow"
SERVICE_STOP_MOW = "stop_mow"
SERVICE_SET_MOW_HEIGHT = "set_mow_height"
SERVICE_RETURN_TO_DOCK = "return_to_dock"
SERVICE_SET_VOICE_VOLUME = "set_voice_volume"
SERVICE_SET_CUSTOM_MOWING_DIRECTION = "set_custom_mowing_direction"

ATTR_SERIAL_NUMBER = "serial_number"
ATTR_MOW_HEIGHT = "mow_height"
ATTR_VOICE_VOLUME = "voice_volume"
ATTR_MOW_DIRECTION = "mow_direction"
ATTR_ENABLE_CUSTOM_DIRECTION = "enable_custom_direction"

# Defaults embedded in Anthbot mobile app auth flow.
DEFAULT_IOT_REGION = "us-east-1"
DEFAULT_IOT_ENDPOINT = "a2bhy9nr7jkgaj-ats.iot.us-east-1.amazonaws.com"
IOT_ENDPOINT_TEMPLATE = "a2bhy9nr7jkgaj-ats.iot.{region}.amazonaws.com"
CN_NORTHWEST_IOT_ENDPOINT = "a2iw0czxjowiip-ats.iot.cn-northwest-1.amazonaws.com.cn"

AWS_ACCESS_KEY_DEFAULT = "AKIAV2C4RVIAOLEXB545"
AWS_SECRET_KEY_DEFAULT = "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"

AWS_ACCESS_KEY_CN = "AKIAWJ3KIT7IV6AHMJ5V"
AWS_SECRET_KEY_CN = "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"

AWS_ACCESS_KEY_CN_NORTHWEST = "AKIAYVWVSSRF7W5YWI74"
AWS_SECRET_KEY_CN_NORTHWEST = "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"

# Country list for login (areaCode in Anthbot API).
COUNTRY_AREA_CODES: tuple[tuple[str, str], ...] = (
    ("Australia (+61)", "61"),
    ("Austria (+43)", "43"),
    ("Belgium (+32)", "32"),
    ("Brazil (+55)", "55"),
    ("United States / Canada (+1)", "1"),
    ("China (+86)", "86"),
    ("Czech Republic (+420)", "420"),
    ("Denmark (+45)", "45"),
    ("Finland (+358)", "358"),
    ("France (+33)", "33"),
    ("Germany (+49)", "49"),
    ("Greece (+30)", "30"),
    ("Hungary (+36)", "36"),
    ("India (+91)", "91"),
    ("Ireland (+353)", "353"),
    ("Italy (+39)", "39"),
    ("Japan (+81)", "81"),
    ("Luxembourg (+352)", "352"),
    ("Mexico (+52)", "52"),
    ("Netherlands (+31)", "31"),
    ("New Zealand (+64)", "64"),
    ("Norway (+47)", "47"),
    ("Poland (+48)", "48"),
    ("Portugal (+351)", "351"),
    ("Romania (+40)", "40"),
    ("Singapore (+65)", "65"),
    ("Slovakia (+421)", "421"),
    ("South Africa (+27)", "27"),
    ("South Korea (+82)", "82"),
    ("Spain (+34)", "34"),
    ("Sweden (+46)", "46"),
    ("Switzerland (+41)", "41"),
    ("Turkey (+90)", "90"),
    ("Ukraine (+380)", "380"),
    ("United Arab Emirates (+971)", "971"),
    ("United Kingdom (+44)", "44"),
)
