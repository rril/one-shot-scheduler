"""Schedule manager for One Shot Scheduler."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import logging
from typing import Any, Callable
from uuid import uuid4

from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import EVENT_UPDATED, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class OneShotSchedule:
    """A single one-shot switch schedule."""

    id: str
    entity_id: str
    start: str
    end: str
    created_at: str

    @property
    def start_dt(self) -> datetime:
        """Return start in UTC."""
        parsed = dt_util.parse_datetime(self.start)
        if parsed is None:
            raise ValueError(f"Invalid start datetime: {self.start}")
        return dt_util.as_utc(parsed)

    @property
    def end_dt(self) -> datetime:
        """Return end in UTC."""
        parsed = dt_util.parse_datetime(self.end)
        if parsed is None:
            raise ValueError(f"Invalid end datetime: {self.end}")
        return dt_util.as_utc(parsed)


class OneShotScheduleManager:
    """Persist and execute one-shot schedules."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self._schedules: dict[str, OneShotSchedule] = {}
        self._unsubs: dict[str, list[Callable[[], None]]] = {}
        self._listeners: list[Callable[[], None]] = []

    @property
    def schedules(self) -> list[OneShotSchedule]:
        """Return schedules sorted by start time."""
        return sorted(self._schedules.values(), key=lambda item: item.start_dt)

    async def async_initialize(self) -> None:
        """Load schedules and restore pending work."""
        stored = await self._store.async_load() or {}
        raw_schedules = stored.get("schedules", [])

        for item in raw_schedules:
            try:
                schedule = OneShotSchedule(**item)
                _ = schedule.start_dt
                _ = schedule.end_dt
            except (TypeError, ValueError):
                _LOGGER.warning("Ignoring invalid stored one-shot schedule: %s", item)
                continue
            self._schedules[schedule.id] = schedule

        await self._async_restore_after_startup()

    async def async_shutdown(self) -> None:
        """Cancel all in-memory listeners."""
        for unsubs in self._unsubs.values():
            for unsub in unsubs:
                unsub()
        self._unsubs.clear()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to schedule changes."""
        self._listeners.append(listener)

        @callback
        def remove_listener() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove_listener

    async def async_create(
        self, entity_id: str, start: datetime, end: datetime
    ) -> OneShotSchedule:
        """Create and arm a one-shot schedule."""
        state = self.hass.states.get(entity_id)
        if state is None:
            raise HomeAssistantError(f"Entity {entity_id} does not exist")
        if entity_id.split(".", 1)[0] != "switch":
            raise HomeAssistantError("One Shot Scheduler currently accepts switch entities only")

        start_utc = dt_util.as_utc(start)
        end_utc = dt_util.as_utc(end)
        now = dt_util.utcnow()

        if end_utc <= start_utc:
            raise HomeAssistantError("End time must be after start time")
        if end_utc <= now:
            raise HomeAssistantError("End time must be in the future")

        schedule = OneShotSchedule(
            id=uuid4().hex[:12],
            entity_id=entity_id,
            start=start_utc.isoformat(),
            end=end_utc.isoformat(),
            created_at=now.isoformat(),
        )
        self._schedules[schedule.id] = schedule
        self._arm_schedule(schedule)
        await self._async_save()

        if start_utc <= now < end_utc:
            await self._async_apply_entity_state(entity_id, now)

        self._notify_updated()
        return schedule

    async def async_cancel(self, schedule_id: str) -> bool:
        """Cancel a schedule. If active, restore the entity based on remaining schedules."""
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return False

        now = dt_util.utcnow()
        was_active = schedule.start_dt <= now < schedule.end_dt
        entity_id = schedule.entity_id

        self._remove_schedule(schedule_id)
        await self._async_save()

        if was_active:
            await self._async_apply_entity_state(entity_id, now)

        self._notify_updated()
        return True

    async def async_clear(self) -> None:
        """Cancel every schedule, turning off entities whose active schedule was removed."""
        now = dt_util.utcnow()
        active_entities = {
            schedule.entity_id
            for schedule in self._schedules.values()
            if schedule.start_dt <= now < schedule.end_dt
        }

        for schedule_id in list(self._schedules):
            self._remove_schedule(schedule_id)
        await self._async_save()

        for entity_id in active_entities:
            await self._async_apply_entity_state(entity_id, now)

        self._notify_updated()

    async def _async_restore_after_startup(self) -> None:
        """Reconcile schedules after a Home Assistant restart."""
        now = dt_util.utcnow()
        expired_entities: set[str] = set()
        active_entities: set[str] = set()
        removed = False

        for schedule_id, schedule in list(self._schedules.items()):
            if schedule.end_dt <= now:
                expired_entities.add(schedule.entity_id)
                self._remove_schedule(schedule_id)
                removed = True
                continue

            if schedule.start_dt <= now < schedule.end_dt:
                active_entities.add(schedule.entity_id)
            self._arm_schedule(schedule)

        for entity_id in active_entities | expired_entities:
            await self._async_apply_entity_state(entity_id, now)

        if removed:
            await self._async_save()
        self._notify_updated()

    @callback
    def _arm_schedule(self, schedule: OneShotSchedule) -> None:
        """Attach one-shot time listeners for future boundaries."""
        self._cancel_listeners(schedule.id)
        now = dt_util.utcnow()
        unsubs: list[Callable[[], None]] = []

        if schedule.start_dt > now:
            unsubs.append(
                async_track_point_in_utc_time(
                    self.hass,
                    lambda _now, sid=schedule.id: self.hass.async_create_task(
                        self._async_handle_start(sid)
                    ),
                    schedule.start_dt,
                )
            )

        if schedule.end_dt > now:
            unsubs.append(
                async_track_point_in_utc_time(
                    self.hass,
                    lambda _now, sid=schedule.id: self.hass.async_create_task(
                        self._async_handle_end(sid)
                    ),
                    schedule.end_dt,
                )
            )

        self._unsubs[schedule.id] = unsubs

    async def _async_handle_start(self, schedule_id: str) -> None:
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return
        await self._async_apply_entity_state(schedule.entity_id, dt_util.utcnow())
        self._notify_updated()

    async def _async_handle_end(self, schedule_id: str) -> None:
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return

        entity_id = schedule.entity_id
        self._remove_schedule(schedule_id)
        await self._async_save()
        await self._async_apply_entity_state(entity_id, dt_util.utcnow())
        self._notify_updated()

    async def _async_apply_entity_state(self, entity_id: str, now: datetime) -> None:
        """Turn entity on iff at least one schedule currently covers now."""
        should_be_on = any(
            schedule.entity_id == entity_id
            and schedule.start_dt <= now < schedule.end_dt
            for schedule in self._schedules.values()
        )
        service = SERVICE_TURN_ON if should_be_on else SERVICE_TURN_OFF
        await self.hass.services.async_call(
            "homeassistant",
            service,
            {"entity_id": entity_id},
            blocking=True,
        )

    @callback
    def _remove_schedule(self, schedule_id: str) -> None:
        self._cancel_listeners(schedule_id)
        self._schedules.pop(schedule_id, None)

    @callback
    def _cancel_listeners(self, schedule_id: str) -> None:
        for unsub in self._unsubs.pop(schedule_id, []):
            unsub()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"schedules": [asdict(schedule) for schedule in self._schedules.values()]}
        )

    @callback
    def _notify_updated(self) -> None:
        for listener in list(self._listeners):
            listener()
        self.hass.bus.async_fire(EVENT_UPDATED)
