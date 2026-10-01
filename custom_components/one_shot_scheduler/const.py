"""Constants for One Shot Scheduler."""

DOMAIN = "one_shot_scheduler"
STORAGE_KEY = f"{DOMAIN}.schedules"
STORAGE_VERSION = 1
CONF_OVERVIEW_SHORTCUTS = "overview_shortcuts"
PLATFORMS = ["sensor"]

SERVICE_CREATE = "create"
SERVICE_ADD_TIME = "add_time"
SERVICE_CANCEL = "cancel"
SERVICE_CLEAR = "clear"

EVENT_UPDATED = f"{DOMAIN}_updated"
CARD_URL = "/one_shot_scheduler/one-shot-scheduler-card.js"
PANEL_URL = "/one_shot_scheduler/one-shot-scheduler-panel.js"
PANEL_PATH = "one-shot-scheduler"
PANEL_ELEMENT = "one-shot-scheduler-panel"

FRONTEND_VERSION = "0.5.2"
