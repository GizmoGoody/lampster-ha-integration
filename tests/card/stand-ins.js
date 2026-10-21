/**
 * Stand-ins for the Home Assistant frontend parts The Lampster card uses,
 * for testing the card in a plain browser page.
 *
 * They use Home Assistant's element names, structure, class names and the
 * CSS the card depends on (copied from the Home Assistant frontend). Like
 * the real ones, the controls carry the "hass" object, which refers back to
 * itself, so code that tries to turn them into text fails here as it would
 * in Home Assistant.
 */

// The hass object: refers back to itself, like Home Assistant's
window.makeHass = (attributes = {}, state = "on") => {
  const hass = {
    states: {
      "light.the_lampster": {
        entity_id: "light.the_lampster",
        state,
        attributes: { rgb_color: [51, 51, 255], brightness: 150, ...attributes },
      },
    },
    entities: { "light.the_lampster": { platform: "lampster" } },
  };
  hass.connection = { hass };
  return hass;
};
const sharedHass = window.makeHass();

class StandIn extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.hass = sharedHass;  // like Home Assistant's controls
  }
}

// ha-control-slider: the slider used by brightness and color temperature
const sliderCss = (value, background, opacity) => `<style>
  :host { display: block; --control-slider-color: var(--feature-color, #33f); --control-slider-background: ${background};
    --control-slider-background-opacity: ${opacity}; --control-slider-thickness: var(--feature-height, 42px);
    --control-slider-border-radius: var(--feature-border-radius, 12px); height: var(--control-slider-thickness); width: 100%; }
  .container { position: relative; height: 100%; width: 100%; --handle-size: 4px; --handle-margin: calc(var(--control-slider-thickness) / 8); }
  .slider { position: relative; height: 100%; width: 100%; border-radius: var(--control-slider-border-radius); overflow: hidden; }
  .slider .slider-track-background { position: absolute; inset: 0; background: var(--control-slider-background); opacity: var(--control-slider-background-opacity); }
  .slider .slider-track-bar { --slider-size: calc(100% - 2 * var(--handle-margin) - var(--handle-size)); position: absolute; height: 100%; width: 100%;
    top: 0; left: 0; background-color: ${opacity >= 1 ? "transparent" : "var(--control-slider-color)"};
    border-radius: min(var(--control-slider-border-radius), 8px); transform: translate3d(calc((${value} - 1) * var(--slider-size)), 0, 0); }
  .slider .slider-track-bar::after { display: block; content: ""; position: absolute; margin: auto; border-radius: 4px; background-color: white;
    top: 0; bottom: 0; right: var(--handle-margin); height: 50%; width: 4px; }
</style><div class="container"><div class="slider"><div class="slider-track-background"></div><div class="slider-track-bar"></div></div></div>`;
customElements.define("ha-control-slider", class extends StandIn {
  connectedCallback() {
    const temp = this.getAttribute("kind") === "temp";
    this.shadowRoot.innerHTML = temp
      ? sliderCss(0.2, "linear-gradient(90deg, #ffb36b, #fff4e8 70%, #fff)", 1)
      : sliderCss(0.59, "var(--control-slider-color)", 0.2);
  }
});

// ha-favorite-color-button: one color favorite
customElements.define("ha-favorite-color-button", class extends StandIn {
  connectedCallback() {
    this.shadowRoot.innerHTML = `<style>
      :host { display: block; }
      button { position: relative; display: block; width: 100%; height: 100%; border: 1px solid transparent; padding: 0; margin: 0;
        border-radius: var(--ha-favorite-color-button-border-radius, 9999px); transition: box-shadow 180ms, transform 180ms; }
      button:active { transform: scale(1.1); }
    </style><button style="background-color: ${this.getAttribute("color")}"></button>`;
  }
});

// ha-control-switch: the toggle
customElements.define("ha-control-switch", class extends StandIn {
  connectedCallback() {
    this.shadowRoot.innerHTML = `<style>
      :host { display: block; --control-switch-on-color: var(--feature-color, #33f); --control-switch-off-color: #888;
        --control-switch-background-opacity: 0.2; --control-switch-thickness: var(--feature-height, 42px);
        --control-switch-border-radius: var(--feature-border-radius, 12px); --control-switch-padding: 4px;
        height: var(--control-switch-thickness); width: 100%; box-sizing: border-box; }
      .switch { box-sizing: border-box; position: relative; height: 100%; width: 100%; border-radius: var(--control-switch-border-radius);
        padding: var(--control-switch-padding); display: flex; }
      .switch .background { position: absolute; top: 0; left: 0; height: 100%; width: 100%; border-radius: inherit;
        background-color: var(--control-switch-off-color); opacity: var(--control-switch-background-opacity); }
      .switch .button { width: 50%; height: 100%; border-radius: calc(var(--control-switch-border-radius) - var(--control-switch-padding));
        background-color: var(--control-switch-off-color); display: flex; align-items: center; justify-content: center; }
      .switch[checked] .background { background-color: var(--control-switch-on-color); }
      .switch[checked] .button { transform: translateX(100%); background-color: var(--control-switch-on-color); }
    </style><div class="switch" checked><div class="background"></div><div class="button"><ha-svg-icon></ha-svg-icon></div></div>`;
  }
});
// Home Assistant's feature styles remove the switch's own padding
const featureStyles = `ha-control-switch { --control-switch-padding: 0px; }`;

// hui-card-feature: one feature
const FEATURE_HTML = {
  "light-brightness": () => `<ha-control-slider></ha-control-slider>`,
  "light-color-temp": () => `<ha-control-slider kind="temp"></ha-control-slider>`,
  "light-color-favorites": () => `<div style="display: flex; gap: 12px; height: var(--feature-height, 42px)">${
    ["#ff2222", "#44ff00", "#3333ff", "#55ffff", "#ff22ff"].map((color) =>
      `<ha-favorite-color-button color="${color}" style="flex: 1; height: 100%; --ha-favorite-color-button-border-radius: var(--feature-border-radius, 12px)"></ha-favorite-color-button>`).join("")}</div>`,
  "light-effect": () => `<div data-control style="height: var(--feature-height, 42px); border-radius: var(--feature-border-radius, 12px); background: rgba(255,255,255,.12)"></div>`,
  "toggle": () => `<ha-control-switch></ha-control-switch>`,
};
// The feature's own element (such as hui-toggle-card-feature), holding its control
// A page can set window.featureDelay to render the controls late, like a
// feature whose code loads after the card has drawn
customElements.define("hui-stand-in-card-feature", class extends StandIn {
  connectedCallback() {
    const render = () => {
      this.shadowRoot.innerHTML = `<style>:host { display: block; } ${featureStyles}</style>${FEATURE_HTML[this.getAttribute("type")]()}`;
    };
    if (window.featureDelay) setTimeout(render, window.featureDelay);
    else render();
  }
});
customElements.define("hui-card-feature", class extends StandIn {
  connectedCallback() {
    this.shadowRoot.innerHTML = `<style>:host > * { pointer-events: auto; }</style><hui-stand-in-card-feature type="${this.getAttribute("type")}"></hui-stand-in-card-feature>`;
  }
});

// hui-card-features: a group of features (the tile card has one inline and one below)
customElements.define("hui-card-features", class extends StandIn {
  connectedCallback() {
    const types = this.getAttribute("types").split(",");
    const columns = this.getAttribute("columns") || 1;
    this.shadowRoot.innerHTML = `<style>
      :host { display: grid; grid-template-columns: repeat(${columns}, minmax(0, 1fr)); gap: 12px var(--feature-column-gap); width: 100%;
        --feature-height: 42px; --feature-border-radius: var(--ha-card-features-border-radius, var(--ha-border-radius-lg, 12px));
        --feature-column-gap: 24px; --feature-divider-inset: 12px; }
      .divided { box-sizing: border-box; margin-inline-start: calc(-1 * var(--feature-divider-inset));
        padding-inline-start: var(--feature-divider-inset); border-inline-start: 1px solid rgba(255, 255, 255, .25); }
    </style>` + types.map((type, index) =>
      `<hui-card-feature type="${type}" class="${index % columns > 0 ? "divided" : ""}"></hui-card-feature>`).join("");
  }
});

// hui-tile-card: the tile card, with the options The Lampster card relies on
customElements.define("hui-tile-card", class extends StandIn {
  constructor() {
    super();
    this.updateComplete = Promise.resolve();
  }

  static async getConfigElement() {
    return document.createElement("hui-tile-card-editor");
  }

  setConfig(config) {
    this.config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  get hass() {
    return this._hass;
  }

  getGridOptions() {
    return { columns: 6, rows: 1 };
  }

  render() {
    if (!this.config || !this._hass) return;
    const stateObj = this._hass.states[this.config.entity];
    const picture = this.config.show_entity_picture ? stateObj.attributes.entity_picture : null;
    const features = (this.config.features || []).map((f) => f.type);
    const inline = this.config.features_position === "inline";
    const beside = inline ? features.slice(0, 1) : [];
    const below = inline ? features.slice(1) : features;
    this.shadowRoot.innerHTML = `<style>
      ha-card { display: flex; flex-direction: column; height: 100%; box-sizing: border-box; padding: 10px; gap: 12px;
        background: var(--ha-card-background, var(--card-background-color, #222));
        border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, #444);
        border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px)); }
      .top { display: flex; align-items: center; gap: 10px; }
      ha-tile-icon { display: block; width: 36px; height: 36px; border-radius: var(--ha-tile-icon-border-radius, 50%); overflow: hidden; }
      img { width: 36px; height: 36px; }
      ha-tile-info { flex: 1; color: var(--primary-text-color, #fff); }
      .top hui-card-features { flex: 1.2; }
    </style><ha-card>
      <div class="top"><ha-tile-icon>${picture ? `<img src="${picture}">` : "icon"}</ha-tile-icon><ha-tile-info>The Lampster</ha-tile-info>
      ${beside.length ? `<hui-card-features types="${beside}"></hui-card-features>` : ""}</div>
      ${below.length ? `<hui-card-features columns="${below.length > 1 ? 2 : 1}" types="${below}"></hui-card-features>` : ""}
    </ha-card>`;
  }
});

// hui-tile-card-editor: the tile card's editor, with its form layout in _schema
customElements.define("hui-tile-card-editor", class extends StandIn {
  constructor() {
    super();
    this._schema = () => [
      { name: "entity", selector: { entity: {} } },
      {
        name: "content", type: "expandable", flatten: true, schema: [
          { name: "name", selector: { entity_name: {} } },
          { name: "", type: "grid", schema: [{ name: "icon" }, { name: "color" }, { name: "show_entity_picture" }, { name: "hide_state" }] },
        ],
      },
    ];
  }

  // Like Home Assistant's, it refuses options it does not know
  setConfig(config) {
    const known = ["type", "view_layout", "layout_options", "grid_options", "visibility", "entity", "name", "icon", "color",
      "show_entity_picture", "hide_state", "state_content", "vertical", "tap_action", "hold_action", "double_tap_action",
      "icon_tap_action", "icon_hold_action", "icon_double_tap_action", "features", "features_position", "time_format"];
    const unknown = Object.keys(config).find((key) => !known.includes(key));
    if (unknown) throw new Error(`At path: ${unknown} -- Expected a value of type \`never\`, but received: \`${JSON.stringify(config[unknown])}\``);
    this.config = config;
    this.schemaNames = JSON.stringify(this._schema());
  }
});

window.loadCardHelpers = async () => ({
  createCardElement: (config) => document.createElement(config.type === "tile" ? "hui-tile-card" : "div"),
});
