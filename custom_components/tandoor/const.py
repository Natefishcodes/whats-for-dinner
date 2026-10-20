"""Constants for the Tandoor Recipes integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "tandoor"
LOGGER = logging.getLogger(__package__)

CONF_DINNER_MEAL_TYPES: Final = "dinner_meal_types"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 15  # minutes
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 240

# Meal type names treated as "dinner" when the user has not picked any.
DEFAULT_DINNER_NAMES: Final = ("dinner", "supper", "abendessen", "dîner", "cena")

# How far ahead the coordinator keeps meal plan entries (drives the calendar's next event).
LOOKAHEAD_DAYS: Final = 7

SOURCE_MEAL_PLAN: Final = "meal_plan"
SOURCE_SUGGESTION: Final = "suggestion"
SOURCE_NONE: Final = "none"

CARD_FILENAME: Final = "tandoor-dinner-card.js"
CARD_URL_BASE: Final = "/tandoor_static"
DATA_CARD_REGISTERED: Final = f"{DOMAIN}_card_registered"
