"""Sensor platform for One Shot Scheduler."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .manager import OneShotScheduleManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the schedule summary sensor."""
    manager: OneShotScheduleManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OneShotSchedulerSensor(manager)])


class OneShotSchedulerSensor(SensorEntity):
    """Expose active schedules to Lovelace and automations."""

    _attr_has_entity_name = True
    _attr_name = "Schedules"
    _attr_icon = "mdi:calendar-clock"
    _attr_translation_key = "schedules"

    def __init__(self, manager: OneShotScheduleManager) -> None:
        self._manager = manager
        self._attr_unique_id = f"{DOMAIN}_schedules"
        self._remove_listener = None

    @property
    def native_value(self) -> int:
        return len(self._manager.schedules)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "schedules": [
                {
                    "id": schedule.id,
                    "entity_id": schedule.entity_id,
                    "start": schedule.start,
                    "end": schedule.end,
                    "created_at": schedule.created_at,
                }
                for schedule in self._manager.schedules
            ]
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_listener = self._manager.async_add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
