"""Sensor platform for One Shot Scheduler."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_OVERVIEW_SHORTCUTS, DOMAIN
from .manager import OneShotScheduleManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up scheduler sensors and Overview shortcut entities."""
    manager: OneShotScheduleManager = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [OneShotSchedulerSensor(manager)]

    for entity_id in entry.options.get(CONF_OVERVIEW_SHORTCUTS, []):
        entities.append(OneShotSchedulerShortcutSensor(hass, entity_id))

    async_add_entities(entities)


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


class OneShotSchedulerShortcutSensor(SensorEntity):
    """Favorite-compatible shortcut that opens the scheduler for one switch."""

    _attr_icon = "mdi:timer-outline"
    _attr_translation_key = "shortcut"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, source_entity_id: str) -> None:
        self._source_entity_id = source_entity_id
        source = hass.states.get(source_entity_id)
        source_name = (
            source.attributes.get("friendly_name", source_entity_id)
            if source is not None
            else source_entity_id
        )
        self._attr_translation_placeholders = {"name": source_name}
        self._attr_unique_id = (
            f"{DOMAIN}_{source_entity_id.replace('.', '_')}_shortcut"
        )

    @property
    def native_value(self) -> str:
        return "ready"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {
            "one_shot_scheduler_shortcut": "true",
            "source_entity_id": self._source_entity_id,
        }
