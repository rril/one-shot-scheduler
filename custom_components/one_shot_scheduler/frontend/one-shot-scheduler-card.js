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
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._render();
      this._initialized = true;
    }
    this._updateEntityOptions();
    this._renderSchedules();
  }

  getCardSize() {
    return 5;
  }

  static getStubConfig() {
    return {};
  }

  _isHebrew() {
    return (this._hass?.language || navigator.language || "").toLowerCase().startsWith("he");
  }

  _t(key) {
    const he = {
      title: "הפעלה חד־פעמית",
      switch: "מפסק",
      choose: "בחר מפסק",
      start: "התחלה",
      now: "עכשיו",
      at: "בשעה",
      end: "סיום",
      duration: "אחרי",
      minutes: "דקות",
      create: "קבע הפעלה",
      pending: "תזמונים פעילים",
      none: "אין תזמונים פעילים",
      cancel: "בטל",
      active: "פעיל עכשיו",
      scheduled: "מתוכנן",
      invalid: "יש לבחור זמנים תקינים. זמן הסיום חייב להיות אחרי זמן ההתחלה.",
      failed: "יצירת התזמון נכשלה",
      cancelFailed: "ביטול התזמון נכשל"
    };
    const en = {
      title: "One-shot switch",
      switch: "Switch",
      choose: "Choose a switch",
      start: "Start",
      now: "Now",
      at: "At time",
      end: "End",
      duration: "After",
      minutes: "minutes",
      create: "Schedule",
      pending: "Active schedules",
      none: "No active schedules",
      cancel: "Cancel",
      active: "Active now",
      scheduled: "Scheduled",
      invalid: "Choose valid times. End must be after start.",
      failed: "Failed to create schedule",
      cancelFailed: "Failed to cancel schedule"
    };
    return (this._isHebrew() ? he : en)[key] || key;
  }

  _render() {
    const rtl = this._isHebrew();
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { padding: 16px; direction:${rtl ? "rtl" : "ltr"}; }
        h2 { margin: 0 0 16px; font-size: 1.35rem; font-weight: 500; }
        .field { margin: 12px 0; }
        .label { font-size: .9rem; color: var(--secondary-text-color); margin-bottom: 6px; }
        select, input[type="datetime-local"], input[type="number"] {
          box-sizing: border-box; width: 100%; min-height: 44px; padding: 8px 10px;
          color: var(--primary-text-color); background: var(--card-background-color);
          border: 1px solid var(--divider-color); border-radius: 8px; font: inherit;
        }
        .modes { display:flex; flex-wrap:wrap; gap:12px; align-items:center; }
        .mode { display:flex; gap:6px; align-items:center; cursor:pointer; }
        .inline { display:grid; grid-template-columns: 1fr auto; gap:8px; align-items:center; margin-top:8px; }
        .duration { display:grid; grid-template-columns: minmax(80px, 140px) auto; gap:8px; align-items:center; margin-top:8px; }
        button.primary {
          width:100%; margin-top:16px; min-height:44px; border:0; border-radius:10px;
          background: var(--primary-color); color: var(--text-primary-color, white);
          font: inherit; font-weight:600; cursor:pointer;
        }
        button.primary:disabled { opacity:.55; cursor:default; }
        .error { color: var(--error-color); margin-top:8px; min-height:1.2em; }
        .divider { height:1px; background:var(--divider-color); margin:18px 0 14px; }
        h3 { margin:0 0 10px; font-size:1rem; font-weight:600; }
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

        <div class="field">
          <div class="label">${this._t("start")}</div>
          <div class="modes">
            <label class="mode"><input type="radio" name="startMode" value="now" checked> ${this._t("now")}</label>
            <label class="mode"><input type="radio" name="startMode" value="at"> ${this._t("at")}</label>
          </div>
          <div id="startAtWrap" style="display:none;margin-top:8px"><input id="startAt" type="datetime-local"></div>
        </div>

        <div class="field">
          <div class="label">${this._t("end")}</div>
          <div class="modes">
            <label class="mode"><input type="radio" name="endMode" value="duration" checked> ${this._t("duration")}</label>
            <label class="mode"><input type="radio" name="endMode" value="at"> ${this._t("at")}</label>
          </div>
          <div id="durationWrap" class="duration"><input id="duration" type="number" min="1" step="1" value="30"><span>${this._t("minutes")}</span></div>
          <div id="endAtWrap" style="display:none;margin-top:8px"><input id="endAt" type="datetime-local"></div>
        </div>

        <button id="create" class="primary">${this._t("create")}</button>
        <div id="error" class="error"></div>

        <div class="divider"></div>
        <h3>${this._t("pending")}</h3>
        <div id="schedules"></div>
      </ha-card>`;

    this.shadowRoot.querySelectorAll('input[name="startMode"]').forEach(el => el.addEventListener("change", () => this._syncModeVisibility()));
    this.shadowRoot.querySelectorAll('input[name="endMode"]').forEach(el => el.addEventListener("change", () => this._syncModeVisibility()));
    this.shadowRoot.getElementById("create").addEventListener("click", () => this._createSchedule());
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
    this.shadowRoot.getElementById("startAtWrap").style.display = startMode === "at" ? "block" : "none";
    this.shadowRoot.getElementById("durationWrap").style.display = endMode === "duration" ? "grid" : "none";
    this.shadowRoot.getElementById("endAtWrap").style.display = endMode === "at" ? "block" : "none";
  }

  _updateEntityOptions() {
    if (!this._hass || !this.shadowRoot) return;
    const select = this.shadowRoot.getElementById("entity");
    if (!select) return;
    const current = select.value;
    const switches = Object.values(this._hass.states)
      .filter(s => s.entity_id.startsWith("switch."))
      .sort((a, b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id, this._hass.language));
    const signature = switches.map(s => `${s.entity_id}|${s.attributes.friendly_name || ""}`).join(";");
    if (select.dataset.signature === signature) return;
    select.dataset.signature = signature;
    select.innerHTML = `<option value="">${this._t("choose")}</option>` + switches.map(s => {
      const name = this._escape(s.attributes.friendly_name || s.entity_id);
      return `<option value="${this._escape(s.entity_id)}">${name}</option>`;
    }).join("");
    if (switches.some(s => s.entity_id === current)) select.value = current;
  }

  async _createSchedule() {
    const error = this.shadowRoot.getElementById("error");
    const button = this.shadowRoot.getElementById("create");
    error.textContent = "";
    const entityId = this.shadowRoot.getElementById("entity").value;
    const startMode = this.shadowRoot.querySelector('input[name="startMode"]:checked').value;
    const endMode = this.shadowRoot.querySelector('input[name="endMode"]:checked').value;

    let start = startMode === "now" ? new Date() : new Date(this.shadowRoot.getElementById("startAt").value);
    let end;
    if (endMode === "duration") {
      const minutes = Number(this.shadowRoot.getElementById("duration").value);
      end = new Date(start.getTime() + minutes * 60000);
    } else {
      end = new Date(this.shadowRoot.getElementById("endAt").value);
    }

    if (!entityId || Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      error.textContent = this._t("invalid");
      return;
    }

    button.disabled = true;
    try {
      await this._hass.callService("one_shot_scheduler", "create", {
        entity_id: entityId,
        start: start.toISOString(),
        end: end.toISOString()
      });
    } catch (e) {
      console.error(e);
      error.textContent = `${this._t("failed")}: ${e?.message || e}`;
    } finally {
      button.disabled = false;
    }
  }

  _getScheduleSensor() {
    return Object.values(this._hass?.states || {}).find(s =>
      s.entity_id.startsWith("sensor.") && Array.isArray(s.attributes?.schedules) &&
      (s.attributes?.friendly_name?.includes("Schedules") || s.attributes?.friendly_name?.includes("תזמונים") || s.attributes?.schedules !== undefined)
    );
  }

  _renderSchedules() {
    if (!this.shadowRoot || !this._hass) return;
    const container = this.shadowRoot.getElementById("schedules");
    if (!container) return;
    const sensor = this._getScheduleSensor();
    const schedules = sensor?.attributes?.schedules || [];
    if (!schedules.length) {
      container.innerHTML = `<div class="empty">${this._t("none")}</div>`;
      return;
    }
    const now = Date.now();
    container.innerHTML = schedules.map(item => {
      const entity = this._hass.states[item.entity_id];
      const name = this._escape(entity?.attributes?.friendly_name || item.entity_id);
      const start = new Date(item.start);
      const end = new Date(item.end);
      const active = start.getTime() <= now && now < end.getTime();
      return `<div class="schedule">
        <div>
          <div class="name">${name}</div>
          <div class="times">${this._escape(this._formatDate(start))} → ${this._escape(this._formatDate(end))}</div>
          <div class="status">${active ? this._t("active") : this._t("scheduled")}</div>
        </div>
        <button class="cancel" data-id="${this._escape(item.id)}">${this._t("cancel")}</button>
      </div>`;
    }).join("");
    container.querySelectorAll("button.cancel").forEach(btn => btn.addEventListener("click", () => this._cancelSchedule(btn.dataset.id)));
  }

  _formatDate(date) {
    return new Intl.DateTimeFormat(this._hass.language || undefined, {
      weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
    }).format(date);
  }

  async _cancelSchedule(id) {
    const error = this.shadowRoot.getElementById("error");
    error.textContent = "";
    try {
      await this._hass.callService("one_shot_scheduler", "cancel", { schedule_id: id });
    } catch (e) {
      console.error(e);
      error.textContent = `${this._t("cancelFailed")}: ${e?.message || e}`;
    }
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
}

customElements.define("one-shot-scheduler-card", OneShotSchedulerCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "one-shot-scheduler-card",
  name: "One Shot Scheduler",
  description: "Create one-time on/off schedules for switches",
  preview: false
});
