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

// The card warns instead of failing when it cannot style a control; a test fails on it
const consoleWarn = console.warn;
console.warn = (...args) => {
  problems.push(`console.warn: ${args.map((a) => (a instanceof Error ? `${a.message} ${a.stack}` : a)).join(" ")}`);
  consoleWarn(...args);
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
      // Nothing of the card clips the tile card (its callouts, such as a
      // slider's value tooltip, can extend past the edge); only the
      // decorations are clipped to the rounded outline
      const clipping = [card, frame, tile].filter((el) => el && getComputedStyle(el).overflow !== "visible");
      check(title, clipping.length === 0, `nothing clips the tile card (${clipping.map((el) => el.className || el.localName).join(", ") || "none"})`);
      check(title, [...root.querySelectorAll(".clip")].length === 2 && [...root.querySelectorAll(".clip")].every((el) => getComputedStyle(el).overflow === "hidden"),
        "the decorations are clipped to the outline");

      // The head replaces the tile card's icon
      const img = tile?.shadowRoot.querySelector("ha-tile-icon img");
      check(title, img?.src.startsWith("data:image/svg+xml"), "the head is shown in place of the icon");
      const head = expectations.head?.[title];
      if (head) check(title, decodeURIComponent(img?.src ?? "").includes(`stop-color="${head}"`), `the head is ${head}`);

      // Fasteners: drawn, all on the card, and the top and bottom rows match
      const uses = [...root.querySelectorAll("#fasteners use")].map((u) => {
        const size = parseFloat(u.getAttribute("width"));
        return [parseFloat(u.getAttribute("x")) + size / 2, parseFloat(u.getAttribute("y")) + size / 2];
      });
      if ((config.fasteners?.type ?? "rivets") === "none") {
        check(title, uses.length === 0, "no fasteners");
      } else {
        check(title, uses.length > 0, `fasteners are drawn (${uses.length})`);
        check(title, uses.every(([x, y]) => x > 0 && x < W && y > 0 && y < H), "every fastener is on the card");
        const mirrored = uses.every(([x, y]) => uses.some(([x2, y2]) => Math.abs(x2 - x) < 0.5 && Math.abs(y2 - (H - y)) < 0.5));
        check(title, mirrored, "the top and bottom fasteners match");
      }

      // Features style: Console puts a channel around each feature (each color
      // favorite on its own); Flat and Console keep the texture off them
      const featureEls = tile ? deep(tile, "hui-card-feature") : [];
      const swatches = tile ? deep(tile, "ha-favorite-color-button") : [];
      const areas = featureEls.length - featureEls.filter((f) => deep(f, "ha-favorite-color-button").length).length + swatches.length;
      const style = config.features_style ?? "match";
      const channels = root.querySelectorAll("#channels .channel").length;
      const masked = root.getElementById("texture").innerHTML.includes("clear)");
      const textured = root.getElementById("texture").innerHTML.replace(/<defs>[\s\S]*?<\/defs>/, "").trim().length > 0;
      if (config.style === "none") {
        check(title, channels === 0, "no channels with style none");
      } else if (style === "console") {
        check(title, channels === areas, `a channel around each feature area (${channels} of ${areas})`);
        for (const slider of tile ? deep(tile, "ha-control-slider") : []) {
          const temp = slider.getAttribute("mode") === "cursor";
          check(title, slider.hasAttribute("lampster-channel") === !temp,
            temp ? "the color temperature slider keeps its gradient" : "the brightness slider has the slide look");
          if (temp) {
            check(title, slider.hasAttribute("lampster-loupe") && slider.style.getPropertyValue("--lampster-bezel").includes("conic-gradient"),
              "the color temperature marker is a loupe with a bezel");
            const cursor = slider.shadowRoot.querySelector(".slider-track-cursor");
            const r = cursor?.getBoundingClientRect();
            check(title, r && Math.abs(r.width - r.height) < 0.5 && getComputedStyle(cursor).borderTopLeftRadius === "50%", "the loupe is round");
          }
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
        const origin = frame.getBoundingClientRect();
        const scale = origin.width / frame.offsetWidth;

        // Each channel surrounds its control (not a padded wrapper) with an
        // even gap, and its corners follow the control's
        const controlBoxes = (tile ? deep(tile, "ha-control-slider, ha-control-switch, [data-control], ha-favorite-color-button") : []).map((el) => {
          const r = el.getBoundingClientRect();
          const shape = el.shadowRoot?.querySelector(".slider, .switch, button") ?? el;
          const radius = parseFloat(getComputedStyle(shape).borderTopLeftRadius) || 0;
          const w = r.width / scale, h = r.height / scale;
          return { x: (r.left - origin.left) / scale, y: (r.top - origin.top) / scale, w, h, radius: Math.min(radius, w / 2, h / 2) };
        });
        for (const c of root.querySelectorAll("#channels .channel")) {
          const x = parseFloat(c.style.left), y = parseFloat(c.style.top), w = parseFloat(c.style.width), h = parseFloat(c.style.height);
          const radius = parseFloat(c.style.borderRadius);
          const control = controlBoxes.find((b) => {
            const gap = b.x - x;
            return gap > 0.5 && gap < 4 && Math.abs((b.y - y) - gap) < 1 && Math.abs((w - b.w) / 2 - gap) < 1 && Math.abs((h - b.h) / 2 - gap) < 1;
          });
          check(title, Boolean(control), `the channel at ${Math.round(x)},${Math.round(y)} surrounds its control evenly`);
          if (control) {
            const gap = control.x - x;
            const want = Math.min(control.radius + gap, w / 2, h / 2);
            check(title, Math.abs(radius - want) < 1, `the channel at ${Math.round(x)},${Math.round(y)} follows its control's corners (${radius.toFixed(1)} for ${want.toFixed(1)})`);
          }
        }
      } else {
        check(title, channels === 0, "no channels");
      }
      // The color temperature slider moves in 100 K steps with every features style
      for (const slider of tile ? deep(tile, "ha-control-slider") : []) {
        if (slider.getAttribute("mode") === "cursor") check(title, slider.step === 100, `color temperature steps of 100 K (${slider.step})`);
        if (style !== "console" || config.style === "none") check(title, !slider.hasAttribute("lampster-loupe"), "no loupe outside Console");
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
