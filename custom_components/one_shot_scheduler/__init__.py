"""One Shot Scheduler integration."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CARD_URL,
    DOMAIN,
    PANEL_ELEMENT,
    PANEL_PATH,
    PANEL_URL,
    PLATFORMS,
    SERVICE_CANCEL,
    SERVICE_CLEAR,
    SERVICE_CREATE,
)
from .manager import OneShotScheduleManager

FRONTEND_DIR = Path(__file__).parent / "frontend"
CARD_FILE = FRONTEND_DIR / "one-shot-scheduler-card.js"
PANEL_FILE = FRONTEND_DIR / "one-shot-scheduler-panel.js"

CREATE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("start"): cv.string,
        vol.Required("end"): cv.string,
    }
)
CANCEL_SCHEMA = vol.Schema({vol.Required("schedule_id"): cv.string})


def _parse_datetime(value: str, field: str) -> datetime:
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        raise HomeAssistantError(f"Invalid {field} datetime: {value}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return parsed


def _get_manager(hass: HomeAssistant) -> OneShotScheduleManager:
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError("One Shot Scheduler is not configured")
    return next(iter(entries.values()))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up services and frontend assets."""
    hass.data.setdefault(DOMAIN, {})

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(CARD_URL, str(CARD_FILE), False),
            StaticPathConfig(PANEL_URL, str(PANEL_FILE), False),
        ]
    )
    frontend.add_extra_js_url(hass, CARD_URL)

    async def handle_create(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        start = _parse_datetime(call.data["start"], "start")
        end = _parse_datetime(call.data["end"], "end")
        await manager.async_create(call.data["entity_id"], start, end)

    async def handle_cancel(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        removed = await manager.async_cancel(call.data["schedule_id"])
        if not removed:
            raise HomeAssistantError("Schedule not found")

    async def handle_clear(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        await manager.async_clear()

    hass.services.async_register(
        DOMAIN, SERVICE_CREATE, handle_create, schema=CREATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL, handle_cancel, schema=CANCEL_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_CLEAR, handle_clear)
    return True


async def _register_sidebar_panel(hass: HomeAssistant) -> None:
    """Register the scheduler as a Home Assistant sidebar panel."""
    language = (hass.config.language or "").lower()
    sidebar_title = "תזמון חד־פעמי" if language.startswith("he") else "One Shot Scheduler"


    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        module_url=PANEL_URL,
        sidebar_title=sidebar_title,
        sidebar_icon="mdi:timer-cog-outline",
        require_admin=False,
        config={},
        config_panel_domain=DOMAIN,
        embed_iframe=False,
    )

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    manager = OneShotScheduleManager(hass)
    await manager.async_initialize()
    hass.data[DOMAIN][entry.entry_id] = manager
    await _register_sidebar_panel(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        manager: OneShotScheduleManager = hass.data[DOMAIN].pop(entry.entry_id)
        await manager.async_shutdown()
        if not hass.data[DOMAIN]:
            frontend.async_remove_panel(hass, PANEL_PATH, warn_if_unknown=False)
    return unloaded
