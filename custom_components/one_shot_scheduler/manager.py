"""Schedule manager for One Shot Scheduler."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
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
VALID_ACTIONS = {"on", "off", "none"}


@dataclass(slots=True)
class OneShotSchedule:
    """A single one-shot schedule."""

    id: str
    entity_id: str
    start: str | None
    end: str | None
    start_action: str
    end_action: str
    created_at: str

    @property
    def start_dt(self) -> datetime | None:
        if self.start is None:
            return None
        parsed = dt_util.parse_datetime(self.start)
        if parsed is None:
            raise ValueError(f"Invalid start datetime: {self.start}")
        return dt_util.as_utc(parsed)

    @property
    def end_dt(self) -> datetime | None:
        if self.end is None:
            return None
        parsed = dt_util.parse_datetime(self.end)
        if parsed is None:
            raise ValueError(f"Invalid end datetime: {self.end}")
        return dt_util.as_utc(parsed)

    @property
    def sort_dt(self) -> datetime:
        return self.start_dt or self.end_dt or dt_util.utcnow()


class OneShotScheduleManager:
    """Persist and execute one-shot schedules."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._schedules: dict[str, OneShotSchedule] = {}
        self._unsubs: dict[str, list[Callable[[], None]]] = {}
        self._listeners: list[Callable[[], None]] = []

    @property
    def schedules(self) -> list[OneShotSchedule]:
        return sorted(self._schedules.values(), key=lambda item: item.sort_dt)

    async def async_initialize(self) -> None:
        """Load schedules, including migration from the original on/off format."""
        stored = await self._store.async_load() or {}
        migrated = False

        for raw in stored.get("schedules", []):
            item = dict(raw)
            if "start_action" not in item:
                item["start_action"] = "on"
                migrated = True
            if "end_action" not in item:
                item["end_action"] = "off"
                migrated = True

            try:
                schedule = OneShotSchedule(**item)
                self._validate_schedule_fields(schedule)
            except (TypeError, ValueError):
                _LOGGER.warning("Ignoring invalid stored one-shot schedule: %s", raw)
                continue
            self._schedules[schedule.id] = schedule

        await self._async_restore_after_startup()
        if migrated:
            await self._async_save()

    async def async_shutdown(self) -> None:
        for unsubs in self._unsubs.values():
            for unsub in unsubs:
                unsub()
        self._unsubs.clear()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        @callback
        def remove_listener() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove_listener

    async def async_create(
        self,
        entity_id: str,
        start: datetime | None,
        end: datetime | None,
        start_action: str = "on",
        end_action: str = "off",
    ) -> OneShotSchedule:
        """Create and arm a one-shot schedule with independent boundary actions."""
        self._validate_entity(entity_id)

        if start_action not in VALID_ACTIONS or end_action not in VALID_ACTIONS:
            raise HomeAssistantError("Action must be on, off, or none")
        if start_action == "none" and end_action == "none":
            raise HomeAssistantError("At least one action must do something")
        if start_action != "none" and start is None:
            raise HomeAssistantError("Start time is required when start action is enabled")
        if end_action != "none" and end is None:
            raise HomeAssistantError("End time is required when end action is enabled")

        start_utc = dt_util.as_utc(start) if start is not None else None
        end_utc = dt_util.as_utc(end) if end is not None else None
        now = dt_util.utcnow()

        if start_utc is not None and end_utc is not None and end_utc <= start_utc:
            raise HomeAssistantError("End time must be after start time")
        if start_utc is not None and start_action != "none" and start_utc < now - timedelta(seconds=2):
            raise HomeAssistantError("Start time must not be in the past")
        if end_utc is not None and end_action != "none" and end_utc <= now:
            raise HomeAssistantError("End time must be in the future")

        schedule = OneShotSchedule(
            id=uuid4().hex[:12],
            entity_id=entity_id,
            start=start_utc.isoformat() if start_utc is not None else None,
            end=end_utc.isoformat() if end_utc is not None else None,
            start_action=start_action,
            end_action=end_action,
            created_at=now.isoformat(),
        )
        self._schedules[schedule.id] = schedule
        self._arm_schedule(schedule)
        await self._async_save()

        if start_utc is not None and start_action != "none" and start_utc <= now:
            await self._async_execute_action(entity_id, start_action)
            if end_utc is None:
                self._remove_schedule(schedule.id)
                await self._async_save()

        self._notify_updated()
        return schedule

    async def async_add_time(self, entity_id: str, minutes: int) -> OneShotSchedule:
        """Turn on now and cumulatively extend a standard quick timer."""
        if minutes < 1:
            raise HomeAssistantError("Minutes must be positive")
        self._validate_entity(entity_id)

        now = dt_util.utcnow()
        active = [
            schedule
            for schedule in self._schedules.values()
            if schedule.entity_id == entity_id
            and schedule.start_action == "on"
            and schedule.end_action == "off"
            and schedule.start_dt is not None
            and schedule.end_dt is not None
            and schedule.start_dt <= now < schedule.end_dt
        ]
        base_end = max((schedule.end_dt for schedule in active if schedule.end_dt), default=now)
        new_end = base_end + timedelta(minutes=minutes)

        for schedule in active:
            self._remove_schedule(schedule.id)

        schedule = OneShotSchedule(
            id=uuid4().hex[:12],
            entity_id=entity_id,
            start=now.isoformat(),
            end=new_end.isoformat(),
            start_action="on",
            end_action="off",
            created_at=now.isoformat(),
        )
        self._schedules[schedule.id] = schedule
        self._arm_schedule(schedule)
        await self._async_save()
        await self._async_execute_action(entity_id, "on")
        self._notify_updated()
        return schedule

    async def async_cancel(self, schedule_id: str) -> bool:
        """Cancel a schedule without changing the entity's current state."""
        if schedule_id not in self._schedules:
            return False
        self._remove_schedule(schedule_id)
        await self._async_save()
        self._notify_updated()
        return True

    async def async_clear(self) -> None:
        """Cancel all schedules without changing entity states."""
        for schedule_id in list(self._schedules):
            self._remove_schedule(schedule_id)
        await self._async_save()
        self._notify_updated()

    async def _async_restore_after_startup(self) -> None:
        """Catch up missed actions and re-arm future boundaries."""
        now = dt_util.utcnow()
        changed = False

        for schedule_id, schedule in list(self._schedules.items()):
            start_dt = schedule.start_dt
            end_dt = schedule.end_dt

            if end_dt is not None and end_dt <= now:
                if schedule.end_action != "none":
                    await self._async_execute_action(schedule.entity_id, schedule.end_action)
                self._remove_schedule(schedule_id)
                changed = True
                continue

            if start_dt is not None and start_dt <= now and schedule.start_action != "none":
                await self._async_execute_action(schedule.entity_id, schedule.start_action)
                if end_dt is None:
                    self._remove_schedule(schedule_id)
                    changed = True
                    continue

            self._arm_schedule(schedule)

        if changed:
            await self._async_save()
        self._notify_updated()

    @callback
    def _arm_schedule(self, schedule: OneShotSchedule) -> None:
        self._cancel_listeners(schedule.id)
        now = dt_util.utcnow()
        unsubs: list[Callable[[], None]] = []
        start_dt = schedule.start_dt
        end_dt = schedule.end_dt

        if start_dt is not None and schedule.start_action != "none" and start_dt > now:
            unsubs.append(
                async_track_point_in_utc_time(
                    self.hass,
                    lambda _now, sid=schedule.id: self.hass.async_create_task(
                        self._async_handle_start(sid)
                    ),
                    start_dt,
                )
            )

        if end_dt is not None and schedule.end_action != "none" and end_dt > now:
            unsubs.append(
                async_track_point_in_utc_time(
                    self.hass,
                    lambda _now, sid=schedule.id: self.hass.async_create_task(
                        self._async_handle_end(sid)
                    ),
                    end_dt,
                )
            )

        self._unsubs[schedule.id] = unsubs

    async def _async_handle_start(self, schedule_id: str) -> None:
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return
        await self._async_execute_action(schedule.entity_id, schedule.start_action)

        if schedule.end_dt is None or schedule.end_action == "none":
            self._remove_schedule(schedule_id)
            await self._async_save()
        self._notify_updated()

    async def _async_handle_end(self, schedule_id: str) -> None:
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return
        await self._async_execute_action(schedule.entity_id, schedule.end_action)
        self._remove_schedule(schedule_id)
        await self._async_save()
        self._notify_updated()

    async def _async_execute_action(self, entity_id: str, action: str) -> None:
        if action == "none":
            return
        service = SERVICE_TURN_ON if action == "on" else SERVICE_TURN_OFF
        await self.hass.services.async_call(
            "homeassistant",
            service,
            {"entity_id": entity_id},
            blocking=True,
        )

    def _validate_entity(self, entity_id: str) -> None:
        state = self.hass.states.get(entity_id)
        if state is None:
            raise HomeAssistantError(f"Entity {entity_id} does not exist")
        if entity_id.split(".", 1)[0] != "switch":
            raise HomeAssistantError(
                "One Shot Scheduler currently accepts switch entities only"
            )

    @staticmethod
    def _validate_schedule_fields(schedule: OneShotSchedule) -> None:
        if schedule.start_action not in VALID_ACTIONS or schedule.end_action not in VALID_ACTIONS:
            raise ValueError("Invalid action")
        if schedule.start_action != "none" and schedule.start_dt is None:
            raise ValueError("Missing start time")
        if schedule.end_action != "none" and schedule.end_dt is None:
            raise ValueError("Missing end time")

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
