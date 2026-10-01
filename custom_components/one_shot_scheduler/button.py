"""Button platform for One Shot Scheduler Overview shortcuts."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_OVERVIEW_SHORTCUTS, DOMAIN, EVENT_SHORTCUT_REQUESTED


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one Favorite-compatible shortcut button per configured switch."""
    buttons = [
        OneShotSchedulerShortcutButton(hass, entity_id)
        for entity_id in entry.options.get(CONF_OVERVIEW_SHORTCUTS, [])
    ]
    async_add_entities(buttons)


class OneShotSchedulerShortcutButton(ButtonEntity):
    """Button that asks the current frontend user to open the scheduler."""

    _attr_icon = "mdi:timer-outline"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, source_entity_id: str) -> None:
        self._source_entity_id = source_entity_id
        source = hass.states.get(source_entity_id)
        source_name = (
            source.attributes.get("friendly_name", source_entity_id)
            if source is not None
            else source_entity_id
        )
        self._attr_name = f"{source_name} timer"
        self._attr_unique_id = (
            f"{DOMAIN}_{source_entity_id.replace('.', '_')}_shortcut_button"
        )

    async def async_press(self) -> None:
        """Request navigation in the frontend session that pressed this button."""
        self.hass.bus.async_fire(
            EVENT_SHORTCUT_REQUESTED,
            {"source_entity_id": self._source_entity_id},
            context=self._context,
        )
