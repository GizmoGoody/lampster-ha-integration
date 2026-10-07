/**
 * Checks for The Lampster card test pages. A page adds cards with addCard(),
 * then calls runChecks(); the results go into <pre id="report">, whose
 * data-result is "pass" or "fail" (read by run_card_tests.py).
 */

const problems = [];
const passed = [];
window.addEventListener("error", (ev) => problems.push(`Page error: ${ev.message} (${ev.filename}:${ev.lineno})`));
window.addEventListener("unhandledrejection", (ev) => problems.push(`Unhandled promise rejection: ${ev.reason}`));
const consoleError = console.error;
console.error = (...args) => {
  problems.push(`console.error: ${args.join(" ")}`);
  consoleError(...args);
};

const cards = [];

/** Add a card to the page: a title, its configuration, and an optional size and CSS class. */
window.addCard = (title, config, { height = 112, width = 400, className = "", hass } = {}) => {
  const figure = document.createElement("figure");
  figure.innerHTML = `<figcaption>${title}</figcaption>`;
  const cell = document.createElement("div");
  cell.className = `cell ${className}`;
  cell.style.cssText = `width:${width}px;height:${height}px`;
  const card = document.createElement("lampster-card");
  card.setConfig({ type: "custom:lampster-card", entity: "light.the_lampster", ...config });
  card.hass = hass ?? window.makeHass();
  cell.append(card);
  figure.append(cell);
  document.getElementById("cards").append(figure);
  cards.push({ title, config, card });
  return card;
};

const check = (title, ok, message) => (ok ? passed.push(`${title}: ${message}`) : problems.push(`${title}: ${message}`));

// Elements matching a selector anywhere inside an element's shadow roots
function deep(el, selector) {
  const root = el.shadowRoot;
  if (!root) return [];
  return [...root.querySelectorAll(selector), ...[...root.querySelectorAll("*")].flatMap((child) => deep(child, selector))];
}

/** Check every card once it has settled, then report. */
window.runChecks = (expectations = {}) => {
  setTimeout(() => {
    for (const { title, config, card } of cards) {
      const root = card.shadowRoot;
      const frame = root.querySelector(".frame");
      const W = frame.clientWidth, H = frame.clientHeight;
      const tile = root.querySelector("hui-tile-card");
      check(title, Boolean(tile), "the tile card is inside the card");

      // The head replaces the tile card's icon
      const img = tile?.shadowRoot.querySelector("ha-tile-icon img");
      check(title, img?.src.startsWith("data:image/svg+xml"), "the head is shown in place of the icon");

      // Fasteners: drawn, all on the card, and the top and bottom rows match
      const uses = [...root.querySelectorAll("#fasteners use")].map((u) => {
        const size = parseFloat(u.getAttribute("width"));
        return [parseFloat(u.getAttribute("x")) + size / 2, parseFloat(u.getAttribute("y")) + size / 2];
      });
      if ((config.fasteners ?? "rivets") === "none") {
        check(title, uses.length === 0, "no fasteners");
      } else {
        check(title, uses.length > 0, `fasteners are drawn (${uses.length})`);
        check(title, uses.every(([x, y]) => x > 0 && x < W && y > 0 && y < H), "every fastener is on the card");
        const mirrored = uses.every(([x, y]) => uses.some(([x2, y2]) => Math.abs(x2 - x) < 0.5 && Math.abs(y2 - (H - y)) < 0.5));
        check(title, mirrored, "the top and bottom fasteners match");
      }

      // Features style: Inset puts a channel around each feature (each color
      // favorite on its own); Flat and Inset keep the texture off them
      const featureEls = tile ? deep(tile, "hui-card-feature") : [];
      const swatches = tile ? deep(tile, "ha-favorite-color-button") : [];
      const areas = featureEls.length - featureEls.filter((f) => deep(f, "ha-favorite-color-button").length).length + swatches.length;
      const style = config.features_style ?? "match";
      const channels = root.querySelectorAll("#channels .channel").length;
      const masked = root.getElementById("texture").innerHTML.includes("clear)");
      const textured = root.getElementById("texture").innerHTML.replace(/<defs>[\s\S]*?<\/defs>/, "").trim().length > 0;
      if (config.style === "none") {
        check(title, channels === 0, "no channels with style none");
      } else if (style === "inset") {
        check(title, channels === areas, `a channel around each feature area (${channels} of ${areas})`);
        for (const slider of tile ? deep(tile, "ha-control-slider") : []) {
          const temp = slider.getAttribute("kind") === "temp";
          check(title, slider.hasAttribute("lampster-channel") === !temp,
            temp ? "the color temperature slider keeps its look" : "the brightness slider has the slide look");
        }
        for (const toggle of tile ? deep(tile, "ha-control-switch") : []) {
          check(title, toggle.hasAttribute("lampster-slide"), "the toggle has the slide look");
        }
        if (swatches.length) {
          check(title, swatches.every((s) => s.hasAttribute("lampster-key")), "the color favorites are keys");
          const pressed = swatches.filter((s) => s.hasAttribute("lampster-pressed")).map((s) => s.getAttribute("color"));
          const want = expectations.pressed?.[title];
          if (want !== undefined) check(title, JSON.stringify(pressed) === JSON.stringify(want), `pressed key: ${pressed.join(",") || "none"}`);
        }
        // Each channel lines up with its feature
        const origin = frame.getBoundingClientRect();
        const scale = origin.width / frame.offsetWidth;
        const boxes = featureEls.flatMap((f) => {
          const keys = deep(f, "ha-favorite-color-button");
          return (keys.length ? keys : [f]).map((el) => {
            const r = el.getBoundingClientRect();
            return { x: (r.left - origin.left) / scale, y: (r.top - origin.top) / scale };
          });
        });
        const lined = [...root.querySelectorAll("#channels .channel")].every((c) =>
          boxes.some((b) => Math.abs(parseFloat(c.style.left) - b.x) <= 4 && Math.abs(parseFloat(c.style.top) - b.y) <= 4));
        check(title, lined, "each channel lines up with its feature");
      } else {
        check(title, channels === 0, "no channels");
      }
      if (style !== "match" && config.style !== "none" && textured && areas) {
        check(title, masked, "the texture is kept off the features");
      }
    }
    const report = document.getElementById("report");
    report.dataset.result = problems.length ? "fail" : "pass";
    report.textContent = [...problems.map((p) => `FAIL ${p}`), ...passed.map((p) => `ok   ${p}`)].join("\n");
  }, 2500);
};
