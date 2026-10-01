# One Shot Scheduler for Home Assistant

A Home Assistant custom integration + Lovelace card for creating **one-time switch schedules** directly from a dashboard.

Choose a switch and configure independent one-time actions at the start and/or end. Each boundary can **turn on**, **turn off**, or **do nothing**.

## Features

- Choose any `switch.*` entity from the dashboard card.
- Start **now** or at a chosen date/time.
- Independent start/end actions: **Turn on**, **Turn off**, or **Do nothing**.
- Start-only and end-only schedules, such as “turn on at 18:00” or “turn off at 23:00”.
- Quick buttons **+30 minutes** and **+1 hour** start immediately; repeated presses extend the same active window cumulatively.
- Stop **after N minutes** or at a chosen date/time.
- Multiple schedules can run at the same time.
- Overlapping schedules for the same switch are handled correctly: the switch stays on until the final overlapping schedule ends.
- Schedules are persisted in Home Assistant storage.
- Survives Home Assistant restarts:
  - if HA comes back while a schedule should be active, the switch is turned on;
  - if HA was offline when the end time passed, the stale schedule is removed and the switch is reconciled.
- Cancel pending or active schedules from the card.
- Hebrew and English UI.
- Dedicated full-page Home Assistant sidebar panel (added automatically after setup).
- Entity-specific shortcut card opens the sidebar scheduler with that switch already selected.
- Automatic Overview support: choose switches in the integration options to create one Favorite-compatible shortcut entity per switch. Tapping it opens the scheduler with that switch preselected.

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

## Sidebar panel

After the integration is added under **Settings → Devices & services**, **One Shot Scheduler** appears automatically in the Home Assistant sidebar. The sidebar title is kept in English because Home Assistant panel metadata is instance-wide; the scheduler page itself follows the language of the currently logged-in user.

The sidebar page uses the same scheduler UI and does not require a separate dashboard.

## Dashboard card

The dashboard card is still available if you also want the scheduler inside an existing dashboard. Add a manual card:

```yaml
type: custom:one-shot-scheduler-card
```

The card JavaScript is served and registered by the integration, so no separate Lovelace resource is required.

### Shortcut for a specific switch

Add a shortcut card anywhere in Lovelace:

```yaml
type: custom:one-shot-scheduler-shortcut
entity: switch.boiler
name: דוד - טיימר
icon: mdi:water-boiler
```

Pressing it opens the One Shot Scheduler page with that entity already selected.

You can also navigate directly to:

`/one-shot-scheduler?entity=switch.boiler`

### Quick timer buttons

With a switch selected, **+30 minutes** or **+1 hour** turns it on immediately. Each additional press extends the current active end time. For example, pressing **+1 hour** twice results in a two-hour active window.

## Services / actions

### Create a schedule

```yaml
action: one_shot_scheduler.create
data:
  entity_id: switch.boiler
  start_action: "on"
  start: "2026-10-01T18:30:00+03:00"
  end_action: "off"
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


## Automatic Overview / Favorites

Home Assistant's automatic Overview only accepts entity Favorites, not arbitrary custom cards. One Shot Scheduler works around that cleanly by creating a dedicated shortcut entity for each switch you choose.

1. Go to **Settings → Devices & services → One Shot Scheduler → Configure**.
2. Select the switches you want shortcuts for.
3. The integration reloads automatically and creates one shortcut button per selected switch, with a friendly name such as **Boiler timer**.
4. Edit the automatic Overview's **Favorites** and add those shortcut entities.
5. Tapping a shortcut Favorite opens **One Shot Scheduler** with that switch already selected, ready for choosing start/end time or using the quick +30 minute / +1 hour buttons.

Versions 0.4.x briefly created two quick-timer button entities per switch. Version 0.5.0 removes those legacy entities automatically on startup.
