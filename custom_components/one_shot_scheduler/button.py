"""Button entities for automatic Overview favorites."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_OVERVIEW_SHORTCUTS, DOMAIN
from .manager import OneShotScheduleManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up quick timer buttons selected in integration options."""
    manager: OneShotScheduleManager = hass.data[DOMAIN][entry.entry_id]
    selected = entry.options.get(CONF_OVERVIEW_SHORTCUTS, [])
    entities: list[ButtonEntity] = []

    for entity_id in selected:
        entities.append(OneShotQuickTimerButton(hass, manager, entity_id, 30))
        entities.append(OneShotQuickTimerButton(hass, manager, entity_id, 60))

    async_add_entities(entities)


class OneShotQuickTimerButton(ButtonEntity):
    """A Favorite-compatible quick timer button."""

    _attr_icon = "mdi:timer-plus-outline"
    _attr_has_entity_name = False

    def __init__(
        self,
        hass: HomeAssistant,
        manager: OneShotScheduleManager,
        source_entity_id: str,
        minutes: int,
    ) -> None:
        self._manager = manager
        self._source_entity_id = source_entity_id
        self._minutes = minutes
        source = hass.states.get(source_entity_id)
        source_name = (
            source.attributes.get("friendly_name", source_entity_id)
            if source is not None
            else source_entity_id
        )
        self._attr_translation_key = "quick_30" if minutes == 30 else "quick_60"
        self._attr_translation_placeholders = {"name": source_name}
        self._attr_unique_id = (
            f"{DOMAIN}_{source_entity_id.replace('.', '_')}_quick_{minutes}"
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        return {
            "source_entity_id": self._source_entity_id,
            "minutes": self._minutes,
        }

    async def async_press(self) -> None:
        """Turn the selected switch on now and extend its active timer."""
        await self._manager.async_add_time(self._source_entity_id, self._minutes)
