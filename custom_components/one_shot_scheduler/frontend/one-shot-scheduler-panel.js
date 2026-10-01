class OneShotSchedulerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode:"open" });
    this._hass = null;
    this._card = null;
    this._lastEntity = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._ensureRendered();
    this._applyUrlEntity();
    if (this._card) this._card.hass = hass;
  }

  set panel(panel) { this._panel = panel; }
  set narrow(narrow) { this._narrow = narrow; }

  connectedCallback() {
    this._ensureRendered();
    this._applyUrlEntity();
  }

  _getUrlEntity() {
    return new URLSearchParams(window.location.search).get("entity");
  }

  _applyUrlEntity() {
    if (!this._card) return;
    const entity = this._getUrlEntity();
    if (entity !== this._lastEntity) {
      this._lastEntity = entity;
      this._card.setConfig(entity ? { entity } : {});
      if (this._hass) this._card.hass = this._hass;
    }
  }

  _ensureRendered() {
    if (this._card || !this.shadowRoot) return;
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; min-height:100%; box-sizing:border-box; background:var(--primary-background-color); }
        .page { box-sizing:border-box; max-width:900px; margin:0 auto; padding:24px 16px 40px; }
        @media (max-width:600px) { .page { padding:12px 8px 24px; } }
      </style>
      <div class="page"><one-shot-scheduler-card></one-shot-scheduler-card></div>`;
    this._card = this.shadowRoot.querySelector("one-shot-scheduler-card");
    this._applyUrlEntity();
    if (this._hass) this._card.hass = this._hass;
  }
}

if (!customElements.get("one-shot-scheduler-panel")) {
  customElements.define("one-shot-scheduler-panel", OneShotSchedulerPanel);
}
