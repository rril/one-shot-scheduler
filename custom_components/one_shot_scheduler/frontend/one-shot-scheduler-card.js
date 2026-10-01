// Subscribe to backend shortcut button presses. This avoids relying on
// Home Assistant's More Info event path, which differs across dashboard UIs.
if (!window.__oneShotSchedulerShortcutSubscriptionV1) {
  window.__oneShotSchedulerShortcutSubscriptionV1 = true;

  const installShortcutSubscription = async () => {
    const root = document.querySelector("home-assistant");
    const hass = root?.hass;

    if (!hass?.connection || !hass?.user?.id) {
      window.setTimeout(installShortcutSubscription, 500);
      return;
    }

    try {
      await hass.connection.subscribeEvents((event) => {
        // Button service calls carry the initiating user's context. Only
        // navigate the browser belonging to that user.
        const eventUserId = event?.context?.user_id;
        if (eventUserId && eventUserId !== hass.user.id) return;

        const sourceEntityId = event?.data?.source_entity_id;
        if (!sourceEntityId) return;

        const url = `/one-shot-scheduler?entity=${encodeURIComponent(sourceEntityId)}`;
        history.pushState(null, "", url);
        window.dispatchEvent(new Event("location-changed"));
      }, "one_shot_scheduler_shortcut_requested");
    } catch (err) {
      console.warn("One Shot Scheduler: shortcut subscription failed", err);
      window.setTimeout(installShortcutSubscription, 1500);
    }
  };

  installShortcutSubscription();
}

class OneShotSchedulerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._initialized = false;
  }

  setConfig(config) {
    this._config = config || {};
    if (this._initialized) this._updateEntityOptions(true);
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._render();
      this._initialized = true;
    }
    this._updateEntityOptions();
    this._renderSchedules();
    this._renderQuickStatus();
  }

  getCardSize() { return 6; }
  static getStubConfig() { return {}; }

  _isHebrew() {
    return (this._hass?.language || navigator.language || "").toLowerCase().startsWith("he");
  }

  _t(key) {
    const he = {
      title: "הפעלה חד־פעמית", switch: "מפסק", choose: "בחר מפסק",
      quick: "הפעלה מהירה", quickHint: "כל לחיצה מפעילה מיד ומוסיפה לזמן שכבר נקבע",
      add30: "+30 דקות", add60: "+שעה", activeUntil: "פעיל עד",
      start: "התחלה", now: "עכשיו", at: "בשעה", end: "סיום",
      action: "פעולה", turnOn: "הדלק", turnOff: "כבה", doNothing: "אל תעשה כלום",
      duration: "אחרי", minutes: "דקות", create: "קבע הפעלה",
      pending: "תזמונים פעילים", none: "אין תזמונים פעילים", cancel: "בטל",
      active: "פעיל עכשיו", scheduled: "מתוכנן",
      invalid: "יש לבחור זמנים תקינים. זמן הסיום חייב להיות אחרי זמן ההתחלה.",
      selectFirst: "יש לבחור מפסק קודם", failed: "יצירת התזמון נכשלה",
      cancelFailed: "ביטול התזמון נכשל", quickFailed: "ההפעלה המהירה נכשלה"
    };
    const en = {
      title: "One-shot switch", switch: "Switch", choose: "Choose a switch",
      quick: "Quick start", quickHint: "Each press starts immediately and adds to the already scheduled time",
      add30: "+30 minutes", add60: "+1 hour", activeUntil: "Active until",
      start: "Start", now: "Now", at: "At time", end: "End",
      action: "Action", turnOn: "Turn on", turnOff: "Turn off", doNothing: "Do nothing",
      duration: "After", minutes: "minutes", create: "Schedule",
      pending: "Active schedules", none: "No active schedules", cancel: "Cancel",
      active: "Active now", scheduled: "Scheduled",
      invalid: "Choose valid times. End must be after start.",
      selectFirst: "Choose a switch first", failed: "Failed to create schedule",
      cancelFailed: "Failed to cancel schedule", quickFailed: "Quick start failed"
    };
    return (this._isHebrew() ? he : en)[key] || key;
  }

  _render() {
    const rtl = this._isHebrew();
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { padding:16px; direction:${rtl ? "rtl" : "ltr"}; }
        h2 { margin:0 0 16px; font-size:1.35rem; font-weight:500; }
        h3 { margin:0 0 10px; font-size:1rem; font-weight:600; }
        .field { margin:12px 0; }
        .label { font-size:.9rem; color:var(--secondary-text-color); margin-bottom:6px; }
        select,input[type="datetime-local"],input[type="number"] {
          box-sizing:border-box; width:100%; min-height:44px; padding:8px 10px;
          color:var(--primary-text-color); background:var(--card-background-color);
          border:1px solid var(--divider-color); border-radius:8px; font:inherit;
        }
        .quickbox { margin:14px 0 18px; padding:12px; border:1px solid var(--divider-color); border-radius:12px; }
        .quickrow { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
        .quickbtn {
          min-height:48px; border:1px solid var(--primary-color); border-radius:10px;
          background:var(--card-background-color); color:var(--primary-color);
          font:inherit; font-weight:700; cursor:pointer;
        }
        .quickbtn:disabled { opacity:.45; cursor:default; }
        .quickhint,.quickstatus { color:var(--secondary-text-color); font-size:.85rem; margin-top:8px; }
        .quickstatus { color:var(--primary-text-color); font-weight:500; min-height:1.1em; }
        .modes { display:flex; flex-wrap:wrap; gap:12px; align-items:center; }
        .mode { display:flex; gap:6px; align-items:center; cursor:pointer; }
        .duration { display:grid; grid-template-columns:minmax(80px,140px) auto; gap:8px; align-items:center; margin-top:8px; }
        button.primary {
          width:100%; margin-top:16px; min-height:44px; border:0; border-radius:10px;
          background:var(--primary-color); color:var(--text-primary-color,white);
          font:inherit; font-weight:600; cursor:pointer;
        }
        button.primary:disabled { opacity:.55; cursor:default; }
        .error { color:var(--error-color); margin-top:8px; min-height:1.2em; }
        .divider { height:1px; background:var(--divider-color); margin:18px 0 14px; }
        .schedule { display:grid; grid-template-columns:1fr auto; gap:12px; padding:10px 0; border-top:1px solid var(--divider-color); }
        .schedule:first-of-type { border-top:0; }
        .name { font-weight:600; }
        .times { color:var(--secondary-text-color); font-size:.9rem; margin-top:3px; }
        .status { font-size:.82rem; margin-top:3px; }
        .cancel { border:0; background:transparent; color:var(--primary-color); font:inherit; cursor:pointer; padding:4px 8px; }
        .empty { color:var(--secondary-text-color); padding:4px 0; }
      </style>
      <ha-card>
        <h2>${this._t("title")}</h2>

        <div class="field">
          <div class="label">${this._t("switch")}</div>
          <select id="entity"><option value="">${this._t("choose")}</option></select>
        </div>

        <div class="quickbox">
          <h3>${this._t("quick")}</h3>
          <div class="quickrow">
            <button id="quick30" class="quickbtn">${this._t("add30")}</button>
            <button id="quick60" class="quickbtn">${this._t("add60")}</button>
          </div>
          <div class="quickhint">${this._t("quickHint")}</div>
          <div id="quickStatus" class="quickstatus"></div>
        </div>

        <div class="field">
          <div class="label">${this._t("start")} · ${this._t("action")}</div>
          <select id="startAction">
            <option value="on" selected>${this._t("turnOn")}</option>
            <option value="off">${this._t("turnOff")}</option>
            <option value="none">${this._t("doNothing")}</option>
          </select>
          <div id="startTiming" style="margin-top:10px">
          <div class="modes">
            <label class="mode"><input type="radio" name="startMode" value="now" checked> ${this._t("now")}</label>
            <label class="mode"><input type="radio" name="startMode" value="at"> ${this._t("at")}</label>
          </div>
          <div id="startAtWrap" style="display:none;margin-top:8px"><input id="startAt" type="datetime-local"></div>
          </div>
        </div>

        <div class="field">
          <div class="label">${this._t("end")} · ${this._t("action")}</div>
          <select id="endAction">
            <option value="off" selected>${this._t("turnOff")}</option>
            <option value="on">${this._t("turnOn")}</option>
            <option value="none">${this._t("doNothing")}</option>
          </select>
          <div id="endTiming" style="margin-top:10px">
          <div class="modes">
            <label class="mode"><input type="radio" name="endMode" value="duration" checked> ${this._t("duration")}</label>
            <label class="mode"><input type="radio" name="endMode" value="at"> ${this._t("at")}</label>
          </div>
          <div id="durationWrap" class="duration"><input id="duration" type="number" min="1" step="1" value="30"><span>${this._t("minutes")}</span></div>
          <div id="endAtWrap" style="display:none;margin-top:8px"><input id="endAt" type="datetime-local"></div>
          </div>
        </div>

        <button id="create" class="primary">${this._t("create")}</button>
        <div id="error" class="error"></div>

        <div class="divider"></div>
        <h3>${this._t("pending")}</h3>
        <div id="schedules"></div>
      </ha-card>`;

    this.shadowRoot.querySelectorAll('input[name="startMode"]').forEach(el => el.addEventListener("change", () => this._syncModeVisibility()));
    this.shadowRoot.querySelectorAll('input[name="endMode"]').forEach(el => el.addEventListener("change", () => this._syncModeVisibility()));
    this.shadowRoot.getElementById("startAction").addEventListener("change", () => this._syncModeVisibility());
    this.shadowRoot.getElementById("endAction").addEventListener("change", () => this._syncModeVisibility());
    this.shadowRoot.getElementById("entity").addEventListener("change", () => this._renderQuickStatus());
    this.shadowRoot.getElementById("create").addEventListener("click", () => this._createSchedule());
    this.shadowRoot.getElementById("quick30").addEventListener("click", () => this._addTime(30));
    this.shadowRoot.getElementById("quick60").addEventListener("click", () => this._addTime(60));
    this._setDefaultDateTimes();
  }

  _setDefaultDateTimes() {
    const now = new Date();
    const start = new Date(now.getTime() + 30 * 60 * 1000);
    start.setSeconds(0, 0);
    const end = new Date(start.getTime() + 30 * 60 * 1000);
    this.shadowRoot.getElementById("startAt").value = this._toDateTimeLocal(start);
    this.shadowRoot.getElementById("endAt").value = this._toDateTimeLocal(end);
  }

  _toDateTimeLocal(date) {
    const pad = n => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  _syncModeVisibility() {
    const startMode = this.shadowRoot.querySelector('input[name="startMode"]:checked').value;
    const endMode = this.shadowRoot.querySelector('input[name="endMode"]:checked').value;
    const startAction = this.shadowRoot.getElementById("startAction").value;
    const endAction = this.shadowRoot.getElementById("endAction").value;
    this.shadowRoot.getElementById("startTiming").style.display = startAction === "none" ? "none" : "block";
    this.shadowRoot.getElementById("endTiming").style.display = endAction === "none" ? "none" : "block";
    this.shadowRoot.getElementById("startAtWrap").style.display = startAction !== "none" && startMode === "at" ? "block" : "none";
    this.shadowRoot.getElementById("durationWrap").style.display = endAction !== "none" && endMode === "duration" ? "grid" : "none";
    this.shadowRoot.getElementById("endAtWrap").style.display = endAction !== "none" && endMode === "at" ? "block" : "none";
  }

  _updateEntityOptions(force=false) {
    if (!this._hass || !this.shadowRoot) return;
    const select = this.shadowRoot.getElementById("entity");
    if (!select) return;
    const current = select.value;
    const desired = current || this._config.entity || "";
    const switches = Object.values(this._hass.states)
      .filter(s => s.entity_id.startsWith("switch."))
      .sort((a,b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id, this._hass.language));
    const signature = switches.map(s => `${s.entity_id}|${s.attributes.friendly_name || ""}`).join(";");
    if (!force && select.dataset.signature === signature && (!desired || select.value === desired)) return;
    select.dataset.signature = signature;
    select.innerHTML = `<option value="">${this._t("choose")}</option>` + switches.map(s => {
      const name = this._escape(s.attributes.friendly_name || s.entity_id);
      return `<option value="${this._escape(s.entity_id)}">${name}</option>`;
    }).join("");
    if (switches.some(s => s.entity_id === desired)) select.value = desired;
  }

  _getSchedules() {
    const sensor = Object.values(this._hass?.states || {}).find(s =>
      s.entity_id.startsWith("sensor.") && Array.isArray(s.attributes?.schedules)
    );
    return sensor?.attributes?.schedules || [];
  }

  _renderQuickStatus() {
    if (!this.shadowRoot || !this._hass) return;
    const status = this.shadowRoot.getElementById("quickStatus");
    const entityId = this.shadowRoot.getElementById("entity")?.value;
    if (!status || !entityId) {
      if (status) status.textContent = "";
      return;
    }
    const now = Date.now();
    const active = this._getSchedules()
      .filter(s => s.entity_id === entityId && new Date(s.start).getTime() <= now && now < new Date(s.end).getTime())
      .sort((a,b) => new Date(b.end) - new Date(a.end));
    status.textContent = active.length ? `${this._t("activeUntil")} ${this._formatTime(new Date(active[0].end))}` : "";
  }

  async _addTime(minutes) {
    const error = this.shadowRoot.getElementById("error");
    const entityId = this.shadowRoot.getElementById("entity").value;
    error.textContent = "";
    if (!entityId) {
      error.textContent = this._t("selectFirst");
      return;
    }
    const buttons = [this.shadowRoot.getElementById("quick30"), this.shadowRoot.getElementById("quick60")];
    buttons.forEach(b => b.disabled = true);
    try {
      await this._hass.callService("one_shot_scheduler", "add_time", { entity_id: entityId, minutes });
    } catch (e) {
      console.error(e);
      error.textContent = `${this._t("quickFailed")}: ${e?.message || e}`;
    } finally {
      buttons.forEach(b => b.disabled = false);
    }
  }

  async _createSchedule() {
    const error = this.shadowRoot.getElementById("error");
    const button = this.shadowRoot.getElementById("create");
    error.textContent = "";
    const entityId = this.shadowRoot.getElementById("entity").value;
    const startAction = this.shadowRoot.getElementById("startAction").value;
    const endAction = this.shadowRoot.getElementById("endAction").value;
    const startMode = this.shadowRoot.querySelector('input[name="startMode"]:checked').value;
    const endMode = this.shadowRoot.querySelector('input[name="endMode"]:checked').value;

    let start = null;
    if (startAction !== "none") {
      start = startMode === "now" ? new Date() : new Date(this.shadowRoot.getElementById("startAt").value);
    }

    let end = null;
    if (endAction !== "none") {
      if (endMode === "duration") {
        const minutes = Number(this.shadowRoot.getElementById("duration").value);
        const base = start ?? new Date();
        end = new Date(base.getTime() + minutes * 60000);
      } else {
        end = new Date(this.shadowRoot.getElementById("endAt").value);
      }
    }

    const invalidStart = start && Number.isNaN(start.getTime());
    const invalidEnd = end && Number.isNaN(end.getTime());
    if (!entityId || (startAction === "none" && endAction === "none") || invalidStart || invalidEnd || (start && end && end <= start)) {
      error.textContent = this._t("invalid");
      return;
    }
    button.disabled = true;
    try {
      const data = {
        entity_id: entityId,
        start_action: startAction,
        end_action: endAction
      };
      if (start) data.start = start.toISOString();
      if (end) data.end = end.toISOString();
      await this._hass.callService("one_shot_scheduler", "create", data);
    } catch (e) {
      console.error(e);
      error.textContent = `${this._t("failed")}: ${e?.message || e}`;
    } finally {
      button.disabled = false;
    }
  }

  _renderSchedules() {
    if (!this.shadowRoot || !this._hass) return;
    const container = this.shadowRoot.getElementById("schedules");
    if (!container) return;
    const schedules = this._getSchedules();
    if (!schedules.length) {
      container.innerHTML = `<div class="empty">${this._t("none")}</div>`;
      return;
    }
    const now = Date.now();
    container.innerHTML = schedules.map(item => {
      const entity = this._hass.states[item.entity_id];
      const name = this._escape(entity?.attributes?.friendly_name || item.entity_id);
      const start = item.start ? new Date(item.start) : null;
      const end = item.end ? new Date(item.end) : null;
      const actionLabel = (action) => action === "on" ? this._t("turnOn") : action === "off" ? this._t("turnOff") : this._t("doNothing");
      const parts = [];
      if (start && item.start_action !== "none") parts.push(`${actionLabel(item.start_action)}: ${this._formatDate(start)}`);
      if (end && item.end_action !== "none") parts.push(`${actionLabel(item.end_action)}: ${this._formatDate(end)}`);
      const active = start && end && start.getTime() <= now && now < end.getTime();
      return `<div class="schedule">
        <div>
          <div class="name">${name}</div>
          <div class="times">${this._escape(parts.join(" · "))}</div>
          <div class="status">${active ? this._t("active") : this._t("scheduled")}</div>
        </div>
        <button class="cancel" data-id="${this._escape(item.id)}">${this._t("cancel")}</button>
      </div>`;
    }).join("");
    container.querySelectorAll("button.cancel").forEach(btn => btn.addEventListener("click", () => this._cancelSchedule(btn.dataset.id)));
  }

  _formatDate(date) {
    return new Intl.DateTimeFormat(this._hass.language || undefined, {
      weekday:"short", day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit"
    }).format(date);
  }

  _formatTime(date) {
    return new Intl.DateTimeFormat(this._hass.language || undefined, {
      hour:"2-digit", minute:"2-digit"
    }).format(date);
  }

  async _cancelSchedule(id) {
    const error = this.shadowRoot.getElementById("error");
    error.textContent = "";
    try {
      await this._hass.callService("one_shot_scheduler", "cancel", { schedule_id:id });
    } catch (e) {
      console.error(e);
      error.textContent = `${this._t("cancelFailed")}: ${e?.message || e}`;
    }
  }

  _escape(value) {
    return String(value ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;")
      .replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
  }
}

if (!customElements.get("one-shot-scheduler-card")) {
  customElements.define("one-shot-scheduler-card", OneShotSchedulerCard);
}

class OneShotSchedulerShortcut extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode:"open" });
    this._config = {};
    this._hass = null;
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("entity is required");
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 1; }

  _render() {
    if (!this.shadowRoot || !this._config.entity) return;
    const state = this._hass?.states?.[this._config.entity];
    const name = this._config.name || state?.attributes?.friendly_name || this._config.entity;
    const icon = this._config.icon || "mdi:timer-outline";
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { cursor:pointer; padding:14px 16px; display:flex; align-items:center; gap:12px; }
        ha-icon { color:var(--primary-color); }
        .name { font-weight:600; }
        .sub { font-size:.85rem; color:var(--secondary-text-color); margin-top:2px; }
      </style>
      <ha-card tabindex="0">
        <ha-icon icon="${icon}"></ha-icon>
        <div><div class="name">${name}</div><div class="sub">${this._config.entity}</div></div>
      </ha-card>`;
    const card = this.shadowRoot.querySelector("ha-card");
    const open = () => {
      const url = `/one-shot-scheduler?entity=${encodeURIComponent(this._config.entity)}`;
      history.pushState(null, "", url);
      window.dispatchEvent(new Event("location-changed"));
    };
    card.addEventListener("click", open);
    card.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") open(); });
  }
}

if (!customElements.get("one-shot-scheduler-shortcut")) {
  customElements.define("one-shot-scheduler-shortcut", OneShotSchedulerShortcut);
}

window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === "one-shot-scheduler-card")) {
  window.customCards.push({
    type:"one-shot-scheduler-card",
    name:"One Shot Scheduler",
    description:"Create one-time on/off schedules for switches",
    preview:false
  });
}
if (!window.customCards.some(c => c.type === "one-shot-scheduler-shortcut")) {
  window.customCards.push({
    type:"one-shot-scheduler-shortcut",
    name:"One Shot Scheduler Shortcut",
    description:"Open One Shot Scheduler with a specific switch preselected",
    preview:false
  });
}
