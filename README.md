# One Shot Scheduler for Home Assistant

A Home Assistant custom integration + Lovelace card for creating **one-time switch schedules** directly from a dashboard.

Choose a switch, choose when it starts, then choose an end time **or a duration**. The schedule runs once and removes itself when finished.

## Features

- Choose any `switch.*` entity from the dashboard card.
- Start **now** or at a chosen date/time.
- Stop **after N minutes** or at a chosen date/time.
- Multiple schedules can run at the same time.
- Overlapping schedules for the same switch are handled correctly: the switch stays on until the final overlapping schedule ends.
- Schedules are persisted in Home Assistant storage.
- Survives Home Assistant restarts:
  - if HA comes back while a schedule should be active, the switch is turned on;
  - if HA was offline when the end time passed, the stale schedule is removed and the switch is reconciled.
- Cancel pending or active schedules from the card.
- Hebrew and English UI.

## Installation with HACS

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add:

   `https://github.com/rril/one-shot-scheduler`

4. Select category **Integration**.
5. Install **One Shot Scheduler**.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration**.
8. Search for **One Shot Scheduler** and add it.

## Dashboard card

Add a manual card to a dashboard:

```yaml
type: custom:one-shot-scheduler-card
```

The card JavaScript is served and registered by the integration, so no separate Lovelace resource is required.

## Services / actions

### Create a schedule

```yaml
action: one_shot_scheduler.create
data:
  entity_id: switch.boiler
  start: "2026-10-01T18:30:00+03:00"
  end: "2026-10-01T19:15:00+03:00"
```

### Cancel a schedule

```yaml
action: one_shot_scheduler.cancel
data:
  schedule_id: "012345abcdef"
```

### Clear all schedules

```yaml
action: one_shot_scheduler.clear
```

## Manual installation

Copy `custom_components/one_shot_scheduler` to `/config/custom_components/one_shot_scheduler`, restart Home Assistant, then add the integration from **Settings → Devices & services**.

## License

MIT
