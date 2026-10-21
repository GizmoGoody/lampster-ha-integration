/**
 * The Lampster card: a tile card dressed in a metal or Lampster finish.
 *
 * The card wraps Home Assistant's own tile card, so the layout, actions,
 * features and more-info dialog are exactly the tile card's. It only adds:
 * - a style (finish) drawn behind the tile card, with a raised edge,
 * - fasteners drawn on top of it, clear of the icon and the controls,
 * - the features (such as the brightness slider) on the style, on a flat
 *   patch of it, or inset in a channel pressed into the panel, and
 * - a picture of The Lampster's head in place of the tile card's icon, shown
 *   through the tile card's own "show entity picture" option. The light's
 *   color fills the lens. The picture is built in memory; no files are written.
 *
 * Every tile card option works the same way here. The card's own options:
 *   style, paint_color, pattern, features_style, and
 *   fasteners: { type, color, spacing }
 *
 * Style "none" keeps the tile card's own look from the theme and adds only
 * the head (in paint_color) and the fasteners.
 */

const CARD_TYPE = "lampster-card";
const EDITOR_TYPE = "lampster-card-editor";
const TILE_EDITOR_TYPE = "lampster-tile-card-editor";
const VERSION = "1.1.0";

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

const ARMY = { black: "#2b2b2b", blue: "#2563c9", gold: "#c9a743", green: "#5f8f57", red: "#cf2e1f", white: "#ecebe6" };
const ARTSY = { black: "#262626", gold: "#cfb04f", green: "#79a774", red: "#d9261c", white: "#efefec" };
const COLOR = { black: "#1e1e1e", blue: "#1f63d6", gold: "#cda43c", green: "#2e9b3a", red: "#e0201b" };
const SPLATTER = {
  black: ["#e0201b", "#f2f2f2"], gold: ["#3a2f12", "#fff6d8"], green: ["#f2f2f2", "#1f3a1c"],
  red: ["#1a1a1a", "#f2f2f2"], white: ["#1a1a1a", "#d9261c"],
};
const cap = (s) => s[0].toUpperCase() + s.slice(1);

// Styles, grouped like the collections in The Lampster's shop
const COLLECTIONS = [
  { id: "none", name: "None", styles: [["none", "None"]] },
  { id: "metal", name: "Metal", styles: [
    ["polished", "Polished Aluminum"], ["brushed", "Brushed Aluminum"],
    ["rusted", "Rusted Steel"], ["painted", "Painted"],
  ] },
  { id: "army", name: "Lampster Army", styles: Object.keys(ARMY).map((c) => [`army_${c}`, `Army ${cap(c)}`]) },
  { id: "artsy", name: "Lampster Artsy", styles: Object.keys(ARTSY).map((c) => [`artsy_${c}`, `Artsy ${cap(c)}`]) },
  { id: "color", name: "Lampster Color", styles: Object.keys(COLOR).map((c) => [`color_${c}`, `Color ${cap(c)}`]) },
];
const STYLES = Object.fromEntries(COLLECTIONS.flatMap((c) => c.styles));
const collectionOf = (style) => COLLECTIONS.find((c) => c.styles.some(([id]) => id === style)).id;
// What the Randomize button redraws for a style, if anything
const RANDOMIZED = (style) =>
  style === "polished" ? "polish" : style === "rusted" ? "rust"
    : style.startsWith("army_") ? "wear" : style.startsWith("artsy_") ? "splatter"
      : style === "painted" || style.startsWith("color_") ? "sheen" : null;

// "match" is written out and labeled "Match style" wherever it is offered
const MATCH = ["match", "Match style"];
const FEATURES_STYLES = [MATCH, ["flat", "Flat"], ["inset", "Inset"]];

const FASTENERS = [["rivets", "Rivets"], ["phillips", "Phillips"], ["hex", "Hex"], ["socket", "Socket"], ["none", "None"]];
/**
 * Fastener spacing: the number is how many gaps each long edge is divided
 * into (0 is corners only). An E after it (such as 4E) puts one fastener at
 * each end of a single-row card instead of in its corners. The E is set in
 * YAML only; the editor offers the fractions and keeps an E that is there.
 */
const GAPS = [[0, "Corners"], [2, "1/2"], [4, "1/4"], [8, "1/8"], [16, "1/16"], [32, "1/32"], [64, "1/64"]];
function parseSpacing(value) {
  const m = String(value).trim().match(/^(\d+)\s*(E?)$/i);
  const gaps = m ? Number(m[1]) : NaN;
  if (!GAPS.some(([n]) => n === gaps)) return null;
  return { gaps, ends: Boolean(m[2]), value: m[2] ? `${gaps}E` : gaps };
}

const DEFAULTS = {
  style: "polished",
  features_style: "match",
};
// paint_color: the paint of Painted (panel and head), or of None's head
const DEFAULT_PAINT = { painted: "teal", none: "light-grey" };
const FASTENER_DEFAULTS = { type: "rivets", color: "match", spacing: 4 };
const DEFAULT_PATTERN = 17;
// The card's own options; everything else belongs to the tile card
const OWN_KEYS = ["style", "paint_color", "pattern", "features_style", "fasteners"];
// Options of earlier versions of the card: never passed on to the tile card
// (its editor would refuse them), and removed by the editor
const RETIRED_KEYS = ["head_color", "fastener_color", "fastener_spacing", "single_row_fasteners", "controls_style", "clear_controls"];
const usesPaint = (style) => style === "painted" || style === "none";

function validate(config) {
  if (!config.entity) throw new Error("Specify an entity");
  const c = { ...DEFAULTS, ...config };
  if (!STYLES[c.style]) throw new Error(`Unknown style: ${c.style}`);
  if (usesPaint(c.style)) c.paint_color ??= DEFAULT_PAINT[c.style];
  if (!FEATURES_STYLES.some(([id]) => id === c.features_style)) {
    throw new Error(`features_style must be one of ${FEATURES_STYLES.map(([id]) => id).join(", ")}`);
  }
  const fasteners = config.fasteners ?? {};
  if (typeof fasteners !== "object" || Array.isArray(fasteners)) {
    throw new Error("fasteners must be a group of options: type, color and spacing (such as type: rivets)");
  }
  c.fasteners = { ...FASTENER_DEFAULTS, ...fasteners };
  if (!FASTENERS.some(([id]) => id === c.fasteners.type)) {
    throw new Error(`fasteners type must be one of ${FASTENERS.map(([id]) => id).join(", ")}`);
  }
  const spacing = parseSpacing(c.fasteners.spacing);
  if (!spacing) {
    throw new Error(`fasteners spacing must be one of ${GAPS.map(([n]) => n).join(", ")}, optionally followed by E (such as 4E)`);
  }
  c.fasteners.spacing = spacing.value;
  if (c.pattern !== undefined) c.pattern = Math.abs(Math.round(Number(c.pattern))) || DEFAULT_PATTERN;
  return c;
}

// The tile card's part of the configuration
function tileConfig(config) {
  const tile = { ...config, type: "tile", show_entity_picture: true };
  for (const key of [...OWN_KEYS, ...RETIRED_KEYS]) delete tile[key];
  return tile;
}

// ---------------------------------------------------------------------------
// Colors
// ---------------------------------------------------------------------------

const hex = (rgb) => "#" + rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
const shade = (color, f) => {
  const n = parseInt(color.slice(1), 16);
  return hex([n >> 16, (n >> 8) & 255, n & 255].map((v) => v * f));
};
const luma = (color) => {
  const n = parseInt(color.slice(1), 16);
  return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
};

/**
 * A color from Home Assistant's color picker as #rrggbb: a theme color name
 * (such as "teal") or any CSS color.
 */
let canvas;
function resolveColor(value, element, fallback) {
  if (typeof value !== "string" || !value) return fallback;
  let css = value;
  if (/^[a-z-]+$/.test(value)) {
    css = getComputedStyle(element).getPropertyValue(`--${value}-color`).trim() || value;
  }
  canvas ??= document.createElement("canvas").getContext("2d");
  canvas.fillStyle = "#000001";
  canvas.fillStyle = css;
  const out = canvas.fillStyle;
  if (out === "#000001") return fallback;
  if (out.startsWith("#")) return out;
  const rgb = out.match(/[\d.]+/g);
  return rgb ? hex(rgb.slice(0, 3).map(Number)) : fallback;
}

// ---------------------------------------------------------------------------
// Drawing
// ---------------------------------------------------------------------------

// Seeded random, so a pattern number always draws the same pattern
const rng = (seed) => () => (seed = (seed * 16807 + 1) % 2147483647) / 2147483647;

const GLOSS = "linear-gradient(160deg, rgba(255,255,255,0) 12%, rgba(255,255,255,.24) 45%, rgba(255,255,255,0) 78%)";
const POLISH = "linear-gradient(115deg, rgba(255,255,255,0) 8%, rgba(255,255,255,.5) 42%, rgba(255,255,255,0) 76%)";
const POLISH_SOFT = "linear-gradient(115deg, rgba(255,255,255,0) 8%, rgba(255,255,255,.28) 42%, rgba(255,255,255,0) 76%)";
const ALUMINUM = "linear-gradient(180deg, #aeb3b7 0%, #92989d 45%, #a6abb0 70%, #868c92 100%)";
const POLISHED_SHADING = "linear-gradient(180deg, rgba(255,255,255,.25) 0%, rgba(255,255,255,0) 35%, rgba(0,0,0,0) 70%, rgba(0,0,0,.25) 100%), linear-gradient(180deg, #9ea3a7, #8c9196)";
const POLISHED = [
  "linear-gradient(100deg, rgba(0,0,0,.28) 0%, rgba(0,0,0,0) 12%, rgba(255,255,255,.7) 27%, rgba(255,255,255,0) 42%, rgba(0,0,0,.32) 54%, rgba(0,0,0,0) 64%, rgba(255,255,255,.5) 77%, rgba(255,255,255,0) 90%, rgba(0,0,0,.25) 100%)",
  POLISHED_SHADING,
].join(", ");

// Polished aluminum with randomized reflections: angle, number, place,
// width and strength of the light and dark bands
function polishedBackground(seed) {
  if (seed === undefined) return POLISHED;
  const r = rng(seed * 31 + 3);
  const angle = Math.round(60 + r() * 70);
  const count = 3 + Math.floor(r() * 4);
  const bands = [];
  for (let i = 0; i < count; i++) {
    const light = i % 2 === (r() < 0.5 ? 0 : 1);
    const center = ((i + 0.2 + r() * 0.6) / count) * 100;
    const width = 5 + r() * 16;
    const color = light ? `rgba(255,255,255,${(0.35 + r() * 0.45).toFixed(2)})` : `rgba(0,0,0,${(0.15 + r() * 0.25).toFixed(2)})`;
    const clear = light ? "rgba(255,255,255,0)" : "rgba(0,0,0,0)";
    bands.push(`linear-gradient(${angle}deg, ${clear} ${(center - width).toFixed(1)}%, ${color} ${center.toFixed(1)}%, ${clear} ${(center + width).toFixed(1)}%)`);
  }
  return [...bands, POLISHED_SHADING].join(", ");
}

// A single soft sheen; a pattern number moves and tilts it
function sheen(seed, fallback, strength) {
  if (seed === undefined) return fallback;
  const r = rng(seed * 17 + 5);
  const angle = Math.round(95 + r() * 80);
  const center = 25 + r() * 50, width = 20 + r() * 20;
  return `linear-gradient(${angle}deg, rgba(255,255,255,0) ${(center - width).toFixed(1)}%, ` +
    `rgba(255,255,255,${strength}) ${center.toFixed(1)}%, rgba(255,255,255,0) ${(center + width).toFixed(1)}%)`;
}

// Noise textures shared by the styles; "p" is a prefix that keeps the ids unique per card
function textureFilters(p, seed) {
  const noise = (id, freq, octaves, s, matrix, srgb = false) =>
    `<filter id="${p}${id}" x="0" y="0" width="100%" height="100%"${srgb ? ' color-interpolation-filters="sRGB"' : ""}>` +
    `<feTurbulence type="fractalNoise" baseFrequency="${freq}" numOctaves="${octaves}" seed="${s}"/>` +
    `<feColorMatrix values="${matrix}"/></filter>`;
  return [
    noise("mottle", "0.012 0.03", 3, seed ?? 4, "0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .22 0"),
    noise("mottleDark", "0.008 0.02", 3, (seed ?? 4) + 8, "0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .3 -.05"),
    noise("matte", "0.9", 2, 3, "0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .16 0"),
    noise("matteDark", "0.7", 2, 8, "0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .14 0"),
    noise("rustBlotch", "0.018 0.03", 5, 11, "0 0 0 0 .7  0 0 0 0 .32  0 0 0 0 .11  0 0 0 3 -1.25", true),
    noise("rustScale", "0.05", 5, 21, "0 0 0 0 .22  0 0 0 0 .09  0 0 0 0 .04  0 0 0 6 -3.2", true),
    noise("rustGrain", "0.8", 1, 6, "0 0 0 0 .78  0 0 0 0 .38  0 0 0 0 .14  0 0 0 2.5 -1.4", true),
    noise("rustPits", "0.4", 2, 2, "0 0 0 0 .12  0 0 0 0 .04  0 0 0 0 .02  0 0 0 6 -3.5", true),
    `<filter id="${p}soft"><feGaussianBlur stdDeviation="6"/></filter>`,
    `<filter id="${p}edgeSoft"><feGaussianBlur stdDeviation="2"/></filter>`,
  ].join("");
}

function splatter(colors, W, H, seed) {
  const r = rng(seed * 7919);
  const out = [];
  for (let i = 0; i < 14; i++) {  // long thin drips
    let x = r() * W, y = r() * H, d = `M${x.toFixed(1)} ${y.toFixed(1)}`;
    for (let k = 0; k < 4; k++) {
      x += (r() - 0.5) * 140;
      y += (r() - 0.5) * 60;
      d += ` Q${(x + (r() - 0.5) * 60).toFixed(1)} ${(y + (r() - 0.5) * 40).toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)}`;
    }
    out.push(`<path d="${d}" fill="none" stroke="${colors[i % 2]}" stroke-width="${(0.5 + r() * 1.3).toFixed(2)}" stroke-linecap="round" opacity=".9"/>`);
  }
  for (let i = 0; i < 40; i++) {  // drops
    out.push(`<circle cx="${(r() * W).toFixed(1)}" cy="${(r() * H).toFixed(1)}" r="${(0.4 + r() * 1.6).toFixed(2)}" fill="${colors[i % 2]}"/>`);
  }
  return out.join("");
}

/**
 * What a style looks like: background CSS, an SVG texture, whether it gets
 * the gloss, the head's housing color, the matching fastener color, and
 * whether its text should be dark ("light" style) or light ("dark" style).
 */
function drawStyle(config, paint, p, W, H) {
  const { style } = config;
  const seed = config.pattern ?? DEFAULT_PATTERN;
  const rect = (attrs) => `<rect width="100%" height="100%" ${attrs}/>`;
  const tone = (color) => (luma(color) > 0.6 ? "light" : "dark");
  if (style === "none") {
    // The theme's own tile card: only the head and the fasteners are drawn
    return { bg: "none", svg: "", housing: paint, metal: paint, tone: null, theme: true };
  }
  if (style === "polished") {
    return {
      bg: polishedBackground(config.pattern),
      svg: rect(`filter="url(#${p}mottle)"`) + rect(`filter="url(#${p}mottleDark)"`),
      housing: "#b4b9be", metal: "#c3c8cc", tone: "light",
    };
  }
  if (style === "brushed") {
    return {
      bg: `${POLISH}, radial-gradient(120% 140% at 30% 0%, #c9cdd1 0%, #b3b8bd 50%, #9da3a9 100%)`,
      svg: rect(`filter="url(#${p}matte)"`) + rect(`filter="url(#${p}matteDark)"`),
      housing: "#aeb3b8", metal: "#b8bdc2", tone: "light",
    };
  }
  if (style === "painted") {
    return { bg: `${sheen(config.pattern, POLISH, 0.5)}, linear-gradient(180deg, ${shade(paint, 1.3)}, ${paint} 55%, ${shade(paint, 0.72)})`, svg: "", housing: paint, metal: paint, tone: tone(paint) };
  }
  if (style === "rusted") {
    // Gray metal with heavy rust in patches and a lighter, speckled stain
    // around them; the pattern number moves the patches
    const mask = (id, matrix) =>
      `<filter id="${p}${id}" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">` +
      `<feTurbulence type="fractalNoise" baseFrequency="0.012 0.02" numOctaves="5" seed="${seed}"/>` +
      `<feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  ${matrix}"/></filter>`;
    const use = (f) => rect(`filter="url(#${p}${f})"`);
    return {
      bg: `${POLISH_SOFT}, ${ALUMINUM}`,
      svg: `<defs>${mask("heavy", "0 0 0 10 -5.9")}${mask("light", "0 0 0 3 -1.35")}
              <filter id="${p}specks" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB"><feTurbulence type="fractalNoise" baseFrequency="0.3" numOctaves="2" seed="${seed + 7}"/><feColorMatrix values="0 0 0 0 .5  0 0 0 0 .2  0 0 0 0 .06  0 0 0 6 -3.4"/></filter>
              <mask id="${p}H">${use("heavy")}</mask><mask id="${p}L">${use("light")}</mask></defs>
            ${use("mottleDark")}
            <g mask="url(#${p}L)">${rect('fill="#b0602a" opacity=".5"')}${use("specks")}</g>
            <g mask="url(#${p}H)">${rect('fill="#6a2e12"')}${use("rustBlotch")}${use("rustScale")}${use("rustGrain")}${use("rustPits")}</g>`,
      housing: "#b3aaa2", metal: "#b0a294", tone: "light",
    };
  }
  const [group, c] = style.split("_");
  if (group === "color") {  // glossy solid paint
    const color = COLOR[c];
    return { bg: `${sheen(config.pattern, GLOSS, 0.24)}, linear-gradient(180deg, ${shade(color, 1.25)}, ${color} 50%, ${shade(color, 0.65)})`, svg: "", housing: color, metal: color, tone: tone(color) };
  }
  if (group === "artsy") {  // paint splatter
    const color = ARTSY[c];
    return {
      bg: `linear-gradient(180deg, ${shade(color, 1.15)}, ${color} 55%, ${shade(color, 0.8)})`,
      svg: splatter(SPLATTER[c], W, H, seed + c.length), gloss: true, housing: color, metal: color, tone: tone(color),
    };
  }
  // Army: worn paint showing rust (near-black on Army Red) in patches and
  // along the edges, and a stenciled star
  const color = ARMY[c];
  const star = c === "white" ? "#a3261c" : "#e9e9e6";
  const wear = c === "red" ? "0 0 0 0 .02  0 0 0 0 .015  0 0 0 0 .012" : "0 0 0 0 .42  0 0 0 0 .2  0 0 0 0 .07";
  const edge = c === "red" ? "0 0 0 0 .02  0 0 0 0 .015  0 0 0 0 .012" : "0 0 0 0 .38  0 0 0 0 .18  0 0 0 0 .06";
  const sx = W / 2, sy = H / 2;  // centered on the card
  const points = Array.from({ length: 10 }, (_, i) => {
    const a = -Math.PI / 2 + (i * Math.PI) / 5, r = i % 2 ? 7 : 17;
    return `${(sx + r * Math.cos(a)).toFixed(1)},${(sy + r * Math.sin(a)).toFixed(1)}`;
  }).join(" ");
  return {
    bg: `linear-gradient(180deg, ${shade(color, 1.08)}, ${color} 60%, ${shade(color, 0.82)})`,
    svg: `<defs>
            <filter id="${p}wear" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.045 0.06" numOctaves="4" seed="${seed}"/><feColorMatrix values="${wear}  0 0 0 -14 4.6"/></filter>
            <filter id="${p}edge" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="3" seed="${seed + 50}"/><feColorMatrix values="${edge}  0 0 0 -10 4.3"/></filter>
            <mask id="${p}edgeMask">${rect('fill="white"')}<rect x="16" y="14" width="${Math.max(0, W - 32)}" height="${Math.max(0, H - 28)}" rx="8" fill="black" filter="url(#${p}soft)"/></mask>
          </defs>
          <polygon points="${points}" fill="${star}" opacity=".85"/>
          ${rect(`filter="url(#${p}wear)"`)}
          ${rect(`filter="url(#${p}edge)" mask="url(#${p}edgeMask)"`)}`,
    gloss: true, housing: color, metal: color, tone: tone(color),
  };
}

// Fasteners take their color from "color" on each <use>, so they can match the style or be custom
function fastenerSymbols(p) {
  return `
    <radialGradient id="${p}shine" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#fff" stop-opacity=".85"/><stop offset=".45" stop-color="#fff" stop-opacity=".1"/><stop offset="1" stop-color="#000" stop-opacity=".45"/></radialGradient>
    <linearGradient id="${p}face" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset=".55" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".35"/></linearGradient>
    <symbol id="${p}rivets" viewBox="0 0 12 12">
      <circle cx="6.4" cy="6.9" r="4.6" fill="rgba(0,0,0,.4)"/><circle cx="6" cy="6" r="4.4" fill="currentColor"/><circle cx="6" cy="6" r="4.4" fill="url(#${p}shine)"/>
    </symbol>
    <symbol id="${p}phillips" viewBox="0 0 12 12">
      <circle cx="6.4" cy="6.9" r="5" fill="rgba(0,0,0,.4)"/><circle cx="6" cy="6" r="4.8" fill="currentColor"/><circle cx="6" cy="6" r="4.8" fill="url(#${p}shine)" opacity=".8"/>
      <path d="M6 2.9v6.2M2.9 6h6.2" stroke="rgba(0,0,0,.65)" stroke-width="1.3" stroke-linecap="round"/>
      <path d="M6.35 3.2v5.6M3.2 6.35h5.6" stroke="rgba(255,255,255,.25)" stroke-width=".4"/>
    </symbol>
    <symbol id="${p}hex" viewBox="0 0 12 12">
      <polygon points="6.5,1.4 10.9,3.9 10.9,9 6.5,11.5 2.1,9 2.1,3.9" fill="rgba(0,0,0,.4)"/>
      <polygon points="6,.8 10.5,3.4 10.5,8.6 6,11.2 1.5,8.6 1.5,3.4" fill="currentColor"/>
      <polygon points="6,.8 10.5,3.4 10.5,8.6 6,11.2 1.5,8.6 1.5,3.4" fill="url(#${p}face)"/>
      <polygon points="6,2.4 9.1,4.2 9.1,7.8 6,9.6 2.9,7.8 2.9,4.2" fill="currentColor"/>
      <polygon points="6,2.4 9.1,4.2 9.1,7.8 6,9.6 2.9,7.8 2.9,4.2" fill="url(#${p}shine)" opacity=".55"/>
    </symbol>
    <symbol id="${p}socket" viewBox="0 0 12 12">
      <circle cx="6.4" cy="6.9" r="5" fill="rgba(0,0,0,.4)"/><circle cx="6" cy="6" r="4.8" fill="currentColor"/><circle cx="6" cy="6" r="4.8" fill="url(#${p}face)"/>
      <circle cx="6" cy="6" r="4.1" fill="none" stroke="rgba(255,255,255,.3)" stroke-width=".4"/>
      <polygon points="6,3.7 8,4.85 8,7.15 6,8.3 4,7.15 4,4.85" fill="rgba(0,0,0,.7)"/>
      <polygon points="8,4.85 8,7.15 6,8.3" fill="rgba(255,255,255,.18)"/>
    </symbol>`;
}

/**
 * Where the fasteners go. Every fastener is the same distance (inset) from
 * its nearest edge; the corner ones are measured from the rounded corner.
 *
 * Spacing 0 is corners only; otherwise each long edge is divided into
 * "spacing" gaps, and each short edge is halved again whenever the long-edge
 * gap is at most half of the short edge's current gap.
 *
 * A single-row card can instead have one fastener at each end, centered
 * between the top and bottom (ends), with the top and bottom edges divided
 * by the spacing and none along the ends.
 */
function fastenerPositions(spacing, W, H, radius, inset, ends) {
  if (ends) {
    const points = [[inset, H / 2], [W - inset, H / 2]];
    const gap = (W - 2 * inset) / Math.max(spacing, 1);
    for (let i = 1; i < spacing; i++) points.push([inset + i * gap, inset], [inset + i * gap, H - inset]);
    return points;
  }
  const c = radius - (radius - inset) / Math.SQRT2;
  const points = [[c, c], [W - c, c], [c, H - c], [W - c, H - c]];
  if (!spacing) return points;
  const wide = W >= H;
  const long = wide ? W : H, short = wide ? H : W;
  const L = long - 2 * c, S = short - 2 * c, gap = L / spacing;
  let shortParts = 1;
  while (gap <= S / (shortParts * 2)) shortParts *= 2;
  const add = (a, b) => points.push(wide ? [a, b] : [b, a]);
  for (let i = 1; i < spacing; i++) {
    add(c + i * gap, inset);
    add(c + i * gap, short - inset);
  }
  for (let i = 1; i < shortParts; i++) {
    add(inset, c + (i * S) / shortParts);
    add(long - inset, c + (i * S) / shortParts);
  }
  return points;
}

// The Lampster icon (the integration's icon): housing outline, top ridge,
// lens opening, inner ring (two circles) and the three screws
const ICON = "M21.9903,11.5386c-.0826.3308-.2558.602-.2984.8878v.1504c0,5.2044-4.3393,9.4232-9.6919,9.4232S2.3081,17.7812,2.3081,12.5768c0-.0502.0007-.1504.0007-.1504-.0426-.2858-.2165-.557-.2991-.8878-.0173-.0688-.0092-.2314.0062-.3008.6008-2.691,1.2682-5.4358,1.444-6.0864.4098-1.228,2.0337-2.9294,3.8746-3.064,2.2063-.055,3.9833-.0874,4.6655-.0874s2.4592.0324,4.6655.0874c1.8409.1346,3.4648,1.836,3.8746,3.064.1757.6506.8431,3.3954,1.444,6.0864.0155.0694.0235.232.0062.3008ZM21.2352,11.1522c-.3024-1.4878-.6706-3.1298-1.094-4.8802l-.0276-.1132c-.0476-.194-.0966-.3946-.1496-.5932-.0018-.0064-.0038-.0128-.006-.019-.0658-.184-.1554-.3692-.2664-.5502-.0006-.001-.0012-.002-.0018-.003-.3246-.5132-.7522-.9748-1.2366-1.3346-.5164-.3838-1.0926-.646-1.6666-.7584-.0028-.0006-.0058-.0012-.0086-.0016l-.1402-.0222c-.004-.0006-.008-.0012-.012-.0016l-.145-.0154c-.006-.0006-.012-.001-.018-.0012-.754-.023-1.55-.04-2.3018-.049-.8346-.0072-1.5756-.0108-2.2664-.0108-1.5586,0-2.939.0182-4.2202.0558h-.001c-.0154.0004-.0308.0008-.0462.0012-.0304.0008-.062.0016-.095.0034-.0044.0002-.0086.0006-.013.001,0,0-.1298.0138-.1434.0152-.0034.0004-.007.0008-.0104.0012-.9906.143-1.9546.7256-2.7142,1.6404-.0006.0008-.0014.0016-.002.0024-.2956.3652-.4894.6944-.6096,1.036-.0024.007-.0046.014-.0064.021-.4576,1.814-1.2598,5.5358-1.2678,5.5732-.0274.1274.0518.2534.1784.2838.0188.0046.0378.0068.0564.0068.1064,0,.2032-.0712.2318-.1782.1124-.4228.2394-.9042.3738-1.414.3656-1.3874.78-2.9592,1.0952-4.0684.4254-1.04,1.8198-1.9512,2.992-1.953h.004c1.1432-.0208,2.4286-.0306,4.0454-.0306.8112,0,1.6238.0024,2.4096.0046h.0024c.7114.0048,1.497.0148,2.2716.029l.108.0104c.0582.0086.0918.0136.1126.0164v.0002c1.0414.189,1.9322.7426,2.444,1.5188.0772.1188.1642.2862.2048.394.091.3144.2174.7716.3754,1.359.2472.919.8648,3.2486,1.097,4.1328.0284.1074.1254.179.232.179.018,0,.0364-.002.0546-.0062.1266-.0296.2066-.1544.1808-.2816ZM12.015,4.9077c-4.1974,0-7.6,3.4026-7.6,7.6s3.4026,7.6,7.6,7.6,7.6-3.4026,7.6-7.6-3.4026-7.6-7.6-7.6ZM12.015,19.4077c-1.8431,0-3.5758-.7177-4.879-2.021-1.3032-1.3032-2.021-3.036-2.021-4.879s.7177-3.5758,2.021-4.879c1.3032-1.3032,3.036-2.021,4.879-2.021s3.5758.7177,4.879,2.021c1.3033,1.3032,2.021,3.036,2.021,4.879s-.7177,3.5758-2.021,4.879c-1.3032,1.3033-3.036,2.021-4.879,2.021ZM12.015,18.7077c1.6561,0,3.213-.6449,4.3841-1.8159,1.171-1.171,1.8159-2.728,1.8159-4.3841s-.6449-3.2131-1.8159-4.3841c-1.171-1.171-2.728-1.8159-4.3841-1.8159s-3.213.6449-4.3841,1.8159c-1.171,1.171-1.8159,2.728-1.8159,4.3841s.6449,3.213,1.8159,4.3841c1.171,1.171,2.728,1.8159,4.3841,1.8159ZM11.6614,20.5264c-.1953.1953-.1953.5118,0,.7071s.5118.1953.7071,0,.1953-.5118,0-.7071-.5118-.1953-.7071,0ZM19.1362,8.8045c.2667.0715.5409-.0868.6124-.3536s-.0868-.5409-.3536-.6124-.5409.0868-.6124.3536.0868.5409.3536.6124ZM5.2473,8.1921c-.0715-.2667-.3456-.425-.6124-.3536s-.425.3456-.3536.6124.3456.425.6124.3536.425-.3456.3536-.6124Z";
const ICON_PARTS = ICON.slice(0, -1).split("ZM").map((s, i) => (i ? "M" : "") + s + "Z");
const [HEAD_OUTLINE, HEAD_RIDGE, HEAD_LENS] = ICON_PARTS;
const HEAD_SCREWS = ICON_PARTS.slice(5).join("");

// The head as an image: the light's color (or dark glass when off) fills the lens
function headPicture(lens, housing) {
  const hi = shade(housing, 1.45), lo = shade(housing, 0.6);
  const glass = lens
    ? `<radialGradient id="g" cx="50%" cy="55%" r="60%"><stop offset="0" stop-color="${shade(lens, 1.25)}"/><stop offset=".7" stop-color="${lens}"/><stop offset="1" stop-color="${shade(lens, 0.7)}"/></radialGradient>`
    : `<radialGradient id="g" cx="50%" cy="55%" r="60%"><stop offset="0" stop-color="#3a3f45"/><stop offset="1" stop-color="#1e2125"/></radialGradient>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -.5 24 25.5"><defs>${glass}` +
    `<radialGradient id="h" cx="35%" cy="25%" r="85%"><stop offset="0" stop-color="${hi}"/><stop offset=".55" stop-color="${housing}"/><stop offset="1" stop-color="${lo}"/></radialGradient>` +
    `<radialGradient id="s" cx="35%" cy="30%" r="70%"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#7d848b"/></radialGradient>` +
    `<linearGradient id="r" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity=".55"/><stop offset=".35" stop-color="#000" stop-opacity="0"/></linearGradient>` +
    `<filter id="d" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy=".7" stdDeviation=".7" flood-color="#000" flood-opacity=".6"/></filter></defs>` +
    `<circle cx="12.015" cy="12.5077" r="7.65" fill="url(#g)"/><circle cx="12.015" cy="12.5077" r="7.6" fill="url(#r)"/>` +
    `<path d="M8.2 9.6a5 5 0 0 1 4.4-2.4" stroke="rgba(255,255,255,.55)" stroke-width=".9" fill="none" stroke-linecap="round"/>` +
    `<g filter="url(#d)"><path d="${HEAD_OUTLINE}${HEAD_LENS}" fill="url(#h)" fill-rule="evenodd" stroke="${lo}" stroke-width=".2"/>` +
    `<path d="${HEAD_RIDGE}" fill="rgba(255,255,255,.4)" transform="translate(0 .25)"/><path d="${HEAD_RIDGE}" fill="${shade(housing, 0.45)}"/>` +
    `<path d="${HEAD_SCREWS}" fill="url(#s)" stroke="rgba(0,0,0,.45)" stroke-width=".12"/></g></svg>`;
  return "data:image/svg+xml," + encodeURIComponent(svg);
}

const lensColor = (stateObj) => {
  if (!stateObj || stateObj.state !== "on") return null;
  const rgb = stateObj.attributes.rgb_color;
  return Array.isArray(rgb) ? hex(rgb) : "#fff4e0";
};

// ---------------------------------------------------------------------------
// Features in a channel
// ---------------------------------------------------------------------------

// Elements matching a selector, looking inside shadow roots (a few levels deep)
function findDeep(el, selector, depth = 5) {
  const root = el.shadowRoot;
  if (!root || depth === 0) return [];
  const found = [...root.querySelectorAll(selector)];
  for (const child of root.querySelectorAll("*")) found.push(...findDeep(child, selector, depth - 1));
  return found;
}

// A corner radius as drawn: CSS limits it to half the shorter side, so a
// theme's "pill" radius (such as 9999px) draws as a half circle
const drawnRadius = (radius, w, h) => Math.max(0, Math.min(radius, w / 2, h / 2));

// The corner radius of a control, as drawn, in the card's own pixels: the
// roundest element inside it (through its shadow roots) that is about its
// size. Sizes on screen are divided by the scale (the editor preview zooms);
// the radius from the style is already in the card's own pixels.
function controlRadius(el, scale) {
  const outer = el.getBoundingClientRect();
  let found = 0;
  let stack = [el];
  for (let depth = 0; depth < 6 && stack.length; depth++) {
    const next = [];
    for (const node of stack) {
      for (const child of node.shadowRoot ? node.shadowRoot.querySelectorAll("*") : []) {
        const r = child.getBoundingClientRect();
        if (Math.abs(r.width - outer.width) < 3 * scale && Math.abs(r.height - outer.height) < 3 * scale) {
          const radius = parseFloat(getComputedStyle(child).borderTopLeftRadius) || 0;
          found = Math.max(found, drawnRadius(radius, r.width / scale, r.height / scale));
        }
        if (child.shadowRoot) next.push(child);
      }
    }
    stack = next;
  }
  return found || drawnRadius(12, outer.width / scale, outer.height / scale);
}

// A color as [red, green, blue], from a CSS color such as "rgb(1, 2, 3)"
const rgbOf = (css) => (css.match(/[\d.]+/g) || []).slice(0, 3).map(Number);

/**
 * A slider in a channel: the unused part shows the channel's floor, and
 * the used part looks like a slatted roll-up door sliding along it, with no
 * handle. The slider's shape is not changed, and the channel around it is
 * concentric with it. This styles parts inside Home Assistant's slider; if
 * an update renames them, the slider simply keeps its usual look.
 */
let sliderSheet;
function styleSlider(slider, on) {
  const root = slider.shadowRoot;
  if (!root) return;
  if (!sliderSheet) {
    sliderSheet = new CSSStyleSheet();
    sliderSheet.replaceSync(`
      :host([lampster-channel]) .slider .slider-track-background { opacity: 0; }
      :host([lampster-channel]) .slider .slider-track-bar {
        background-image:
          repeating-linear-gradient(90deg,
            rgba(255,255,255,.28) 0, rgba(255,255,255,.08) 4px, rgba(0,0,0,.12) 8px,
            rgba(0,0,0,.6) 8px, rgba(0,0,0,.6) 10px),
          linear-gradient(180deg, rgba(255,255,255,.3), rgba(255,255,255,0) 40%, rgba(0,0,0,.3));
        box-shadow: inset 0 1px 0 rgba(255,255,255,.3), inset 0 -1px 0 rgba(0,0,0,.35);
      }
      :host([lampster-channel]) .slider .slider-track-bar::after { display: none; }
    `);
  }
  if (!root.adoptedStyleSheets.includes(sliderSheet)) root.adoptedStyleSheets = [...root.adoptedStyleSheets, sliderSheet];
  // Only sliders whose unused part is a dim copy of the bar (such as
  // brightness); a slider showing a scale (such as color temperature's
  // gradient) keeps its look inside the channel
  const opacity = parseFloat(getComputedStyle(slider).getPropertyValue("--control-slider-background-opacity"));
  slider.toggleAttribute("lampster-channel", on && !(opacity >= 1));
}

/**
 * Inset styling for other controls, by an attribute on the control: color
 * favorites as 3D keys that press in when touched (and stay in while they
 * match the light), and the toggle as a slide whose tab is beveled and
 * whose off side shows the channel's floor. Like the slider, this styles
 * parts inside Home Assistant's controls; if an update renames them, they
 * keep their usual look.
 */
const CONTROL_SHEET = `
  :host([lampster-key]) button {
    background-image: linear-gradient(180deg, rgba(255,255,255,.35), rgba(255,255,255,0) 45%, rgba(0,0,0,.18));
    box-shadow: inset 0 1px 0 rgba(255,255,255,.55), inset 0 -2px 2px rgba(0,0,0,.3), 0 2px 3px rgba(0,0,0,.5);
    transition: transform 120ms ease-in-out, box-shadow 120ms ease-in-out;
  }
  :host([lampster-key]) button:active,
  :host([lampster-key][lampster-pressed]) button {
    transform: translateY(1px) scale(.96);
    background-image: linear-gradient(180deg, rgba(0,0,0,.22), rgba(0,0,0,0) 55%, rgba(255,255,255,.08));
    box-shadow: inset 0 2px 4px rgba(0,0,0,.55), inset 0 -1px 0 rgba(255,255,255,.2);
  }
  :host([lampster-slide]) .switch .background,
  :host([lampster-slide]) .switch:hover .background,
  :host([lampster-slide]) .switch:focus-visible .background { opacity: 0 !important; }
  :host([lampster-slide]) { --control-switch-padding: 0px !important; }
  :host([lampster-slide]) .switch { padding: 0 !important; }
  :host([lampster-slide]) .switch .button {
    position: relative;
    background-color: var(--control-switch-on-color);
    background-image:
      linear-gradient(180deg, rgba(255,255,255,.4), rgba(255,255,255,.05) 40%, rgba(0,0,0,.05) 60%, rgba(0,0,0,.3));
    box-shadow:
      inset 0 1px 0 rgba(255,255,255,.6), inset 0 -1px 0 rgba(0,0,0,.35),
      inset 1px 0 0 rgba(255,255,255,.25), inset -1px 0 0 rgba(0,0,0,.25),
      0 1px 2px rgba(0,0,0,.55);
  }
  /* A shallow dish in the tab, for a thumb to rest in */
  :host([lampster-slide]) .switch .button::after {
    content: ""; position: absolute; inset: 4px;
    border-radius: 9999px;
    background: radial-gradient(ellipse at 50% 30%, rgba(0,0,0,.26), rgba(0,0,0,.1) 55%, rgba(255,255,255,.1));
    box-shadow: inset 0 2px 3px rgba(0,0,0,.35), inset 0 -1px 1px rgba(255,255,255,.35);
  }
  :host([lampster-slide]) .switch .button ha-svg-icon,
  :host([lampster-slide]) .switch .button slot { display: none; }
`;
let controlSheet;
function styleControl(control, attribute, on) {
  const root = control.shadowRoot;
  if (!root) return;
  if (!controlSheet) {
    controlSheet = new CSSStyleSheet();
    controlSheet.replaceSync(CONTROL_SHEET);
  }
  if (!root.adoptedStyleSheets.includes(controlSheet)) root.adoptedStyleSheets = [...root.adoptedStyleSheets, controlSheet];
  control.toggleAttribute(attribute, on);
}

// The measured layout as text, to tell whether it moved: positions and
// sizes only. (The controls themselves cannot be turned into text: Home
// Assistant's controls hold data that refers back to itself.)
const layoutSignature = (controls) =>
  [...controls.icon, ...controls.features].map((b) => `${Math.round(b.x)},${Math.round(b.y)},${Math.round(b.w)},${Math.round(b.h)},${Math.round(b.radius ?? 0)}`).join(";");

// ---------------------------------------------------------------------------
// The card
// ---------------------------------------------------------------------------

let instances = 0;

class LampsterCard extends HTMLElement {
  constructor() {
    super();
    this._prefix = `lc${instances++}`;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; height: 100%; }
        .frame {
          position: relative; height: 100%; box-sizing: border-box; overflow: hidden; isolation: isolate;
          /* Exactly the tile card's own corners (ha-card), from the theme */
          border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg));
        }
        .frame.styled { box-shadow: 0 1px 2px rgba(0, 0, 0, .45), 0 4px 10px rgba(0, 0, 0, .3); }
        .frame:not(.styled) #bevel { display: none; }
        .layer { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
        /* A slightly raised panel: lit top and left edges, shaded bottom and right */
        #bevel {
          border-radius: inherit; z-index: 1;
          box-shadow:
            inset 0 1px 0 rgba(255, 255, 255, .55), inset 1px 0 0 rgba(255, 255, 255, .3),
            inset 0 -1px 0 rgba(0, 0, 0, .45), inset -1px 0 0 rgba(0, 0, 0, .3),
            inset 3px 3px 4px -1px rgba(255, 255, 255, .22), inset -3px -3px 5px -1px rgba(0, 0, 0, .3);
        }
        .tile { position: relative; display: block; height: 100%; --ha-tile-icon-border-radius: 0; }
        .styled .tile {
          --ha-card-background: transparent; --card-background-color: transparent;
          --ha-card-box-shadow: none; --ha-card-border-width: 0; --ha-card-border-color: transparent;
        }
        .tile.light { --primary-text-color: #1d2126; --secondary-text-color: #3c434b; text-shadow: 0 1px 0 rgba(255, 255, 255, .5); }
        .tile.dark { --primary-text-color: #f4f4f4; --secondary-text-color: #dadada; text-shadow: 0 1px 2px rgba(0, 0, 0, .8); }
        #fasteners { z-index: 2; }
        /* Channel features: a channel pressed into the panel */
        .channel {
          position: absolute; box-sizing: border-box;
          background: linear-gradient(180deg, rgba(0, 0, 0, .16), rgba(0, 0, 0, .06));
          box-shadow:
            inset 0 2px 3px rgba(0, 0, 0, .5), inset 0 1px 1px rgba(0, 0, 0, .35),
            inset 0 -1px 0 rgba(255, 255, 255, .25), 0 1px 0 rgba(255, 255, 255, .45);
        }
        /* A toggle's channel: a magnetic rail along its middle */
        .channel.rail::before {
          content: ""; position: absolute; left: 12%; right: 12%; top: 50%; height: 3px; margin-top: -1.5px;
          border-radius: 2px;
          background: linear-gradient(180deg, rgba(0, 0, 0, .55), rgba(60, 64, 70, .5) 60%, rgba(255, 255, 255, .25));
          box-shadow: 0 1px 0 rgba(255, 255, 255, .2);
        }
      </style>
      <div class="frame">
        <div class="layer" id="bg"></div>
        <svg class="layer" id="texture"></svg>
        <div class="layer" id="gloss"></div>
        <div class="layer" id="channels"></div>
        <div class="layer" id="bevel"></div>
        <svg class="layer" id="fasteners"></svg>
      </div>`;
    this._frame = this.shadowRoot.querySelector(".frame");
    this._resize = new ResizeObserver(() => this._draw());
    this._resize.observe(this._frame);
  }

  static getConfigElement() {
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig(hass) {
    const entities = Object.keys(hass.states).filter((id) => id.startsWith("light."));
    const entity = entities.find((id) => hass.entities?.[id]?.platform === "lampster") ?? entities[0] ?? "";
    return explicit({ entity, features: [{ type: "light-brightness" }] });
  }

  setConfig(config) {
    this._config = validate(config);
    const tile = tileConfig(config);
    if (this._tile) {
      this._tile.setConfig(tile);
      this._afterTileUpdate();
    } else if (customElements.get("hui-tile-card")) {
      this._createTile(tile);
    } else {
      // The tile card is loaded on demand; the card helpers load it
      window.loadCardHelpers?.().then(async (helpers) => {
        helpers.createCardElement({ type: "tile", entity: tile.entity });
        await customElements.whenDefined("hui-tile-card");
        if (!this._tile) this._createTile(tileConfig(this._config));
      });
    }
    this._draw();
  }

  _createTile(tile) {
    this._tile = document.createElement("hui-tile-card");
    this._tile.classList.add("tile");
    this._tile.setConfig(tile);
    if (this._hass) this._tile.hass = this._innerHass(this._hass);
    if (this._preview !== undefined) this._tile.preview = this._preview;
    if (this._layout !== undefined) this._tile.layout = this._layout;
    this._frame.insertBefore(this._tile, this.shadowRoot.getElementById("bevel"));
    this._afterTileUpdate();
  }

  // Redraw once the tile card has rendered, so the fasteners can avoid its controls
  _afterTileUpdate() {
    const done = this._tile?.updateComplete;
    if (done?.then) done.then(() => this._draw());
    else this._draw();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._tile) this._tile.hass = this._innerHass(hass);
    this._markPressed();
  }

  // Inset: the color favorite matching the light's current color stays pressed
  _markPressed() {
    if (!this._swatches?.length) return;
    const stateObj = this._hass?.states[this._config?.entity];
    const current = stateObj?.state === "on" ? stateObj.attributes.rgb_color : null;
    for (const swatch of this._swatches) {
      const inner = swatch.shadowRoot?.querySelector("button");
      const color = inner ? rgbOf(getComputedStyle(inner).backgroundColor) : [];
      const match = Array.isArray(current) && color.length === 3 && color.every((v, i) => Math.abs(v - current[i]) <= 6);
      swatch.toggleAttribute("lampster-pressed", match);
    }
  }

  get hass() {
    return this._hass;
  }

  // Dashboard properties the tile card uses
  set preview(value) {
    this._preview = value;
    if (this._tile) this._tile.preview = value;
  }

  set layout(value) {
    this._layout = value;
    if (this._tile) this._tile.layout = value;
  }

  getCardSize() {
    if (this._tile?.getCardSize) return this._tile.getCardSize();
    const features = this._config?.features?.length ?? 0;
    return 1 + (this._config?.vertical ? 1 : 0) + features;
  }

  getGridOptions() {
    if (this._tile?.getGridOptions) return this._tile.getGridOptions();
    const inline = this._config?.features_position === "inline" && !this._config?.vertical;
    const features = inline ? 0 : this._config?.features?.length ?? 0;
    return { columns: 6, rows: 1 + features + (this._config?.vertical ? 1 : 0), min_columns: 6, min_rows: 1 };
  }

  /**
   * The Home Assistant object the tile card sees: the same, except that the
   * light's entity picture is the head. The changed state object is reused
   * until the real one or the picture changes, so the tile card does not
   * redraw on unrelated state changes.
   */
  _innerHass(hass) {
    const entity = this._config?.entity;
    const stateObj = hass.states[entity];
    if (!stateObj) return hass;
    const picture = this._picture(stateObj);
    if (this._sourceState !== stateObj || this._lastPicture !== picture) {
      this._sourceState = stateObj;
      this._lastPicture = picture;
      this._innerState = { ...stateObj, attributes: { ...stateObj.attributes, entity_picture: picture } };
    }
    return { ...hass, states: { ...hass.states, [entity]: this._innerState } };
  }

  _picture(stateObj) {
    const housing = this._housing ?? "#b4b9be";
    const lens = lensColor(stateObj);
    const key = `${housing}|${lens}`;
    if (this._pictureKey !== key) {
      this._pictureKey = key;
      this._pictureUrl = headPicture(lens, housing);
    }
    return this._pictureUrl;
  }

  /**
   * Where the tile card's icon and controls are, relative to the card. Read
   * from the tile card's rendered layout; if it ever changes, the fasteners
   * are simply drawn without avoiding them.
   */
  _controls() {
    const root = this._tile?.shadowRoot;
    if (!root) return { icon: [], features: [], sliders: [], swatches: [], switches: [] };
    // Positions in the card's own pixels, even while the card is scaled
    // (the card editor's preview opens with a zoom animation)
    const origin = this._frame.getBoundingClientRect();
    const scale = origin.width / this._frame.offsetWidth || 1;
    const box = (el) => {
      const r = el.getBoundingClientRect();
      return r.width && r.height
        ? { x: (r.left - origin.left) / scale, y: (r.top - origin.top) / scale, w: r.width / scale, h: r.height / scale }
        : null;
    };
    const find = (selector) => [...root.querySelectorAll(selector)].map(box).filter(Boolean);
    // The tile card has up to two groups of features: one beside the name
    // (inline) and one below it
    const groups = [...root.querySelectorAll("hui-card-features")];
    this._watched ??= new WeakSet();
    for (const group of groups) {
      if (this._watched.has(group)) continue;
      this._watched.add(group);
      this._resize.observe(group);
    }
    // The areas the features take: each feature, except that each color
    // favorite counts on its own (so the style shows between them); a group
    // whose features cannot be told apart counts as one. An area's corner
    // radius is its control's, so an inset around it follows the same curve.
    const features = [];
    const sliders = [];
    const swatches = [];
    const switches = [];
    for (const group of groups) {
      const parts = [...(group.shadowRoot?.querySelectorAll("hui-card-feature") ?? [])];
      for (const el of parts) {
        const keys = findDeep(el, "ha-favorite-color-button");
        swatches.push(...keys);
        const slide = findDeep(el, "ha-control-switch").length > 0;
        // The feature itself, not its wrapper: a feature next to a divider
        // line is padded to make room for the line
        const inner = [...(el.shadowRoot?.children ?? [])].find((child) => child.tagName !== "STYLE") ?? el;
        for (const area of keys.length ? keys : [inner]) {
          const b = box(area);
          if (b) features.push({ ...b, radius: controlRadius(area, scale), slide });
        }
        sliders.push(...findDeep(el, "ha-control-slider"));
        switches.push(...findDeep(el, "ha-control-switch"));
      }
      if (!parts.length) features.push(...[box(group)].filter(Boolean).map((b) => ({ ...b, radius: 12 })));
    }
    // Watch for controls that appear later (a feature's code can load after
    // the card has drawn)
    this._watchAdded(root);
    for (const group of groups) this._watchAdded(group.shadowRoot, 6);
    return { icon: find("ha-tile-icon, ha-tile-info"), features, sliders, swatches, switches };
  }

  /**
   * Redraw when elements are added inside a shadow root (and the shadow
   * roots inside it, a few levels deep), such as a feature's control that
   * renders after its code loads. Only additions count, not changes.
   */
  _watchAdded(root, depth = 0) {
    if (!root) return;
    this._observed ??= new WeakSet();
    if (!this._observed.has(root)) {
      this._observed.add(root);
      this._mutations ??= new MutationObserver(() => this._scheduleDraw());
      this._mutations.observe(root, { childList: true, subtree: true });
    }
    if (depth > 0) for (const el of root.querySelectorAll("*")) this._watchAdded(el.shadowRoot, depth - 1);
  }

  // A timer, not the next screen paint: paints stop when nothing on the page
  // changes (and in background tabs), timers still run
  _scheduleDraw() {
    if (this._drawPending) return;
    this._drawPending = true;
    setTimeout(() => {
      this._drawPending = false;
      this._draw();
    }, 0);
  }

  /**
   * After a draw, keep checking the layout (every 50 ms) for about a second: the tile card
   * can move its features without changing size (fonts loading, the editor
   * preview's opening animation, features that render late).
   */
  _settle(signature) {
    this._signature = signature;
    this._settleUntil = performance.now() + 1200;
    if (this._settling) return;
    this._settling = true;
    const check = () => {
      if (performance.now() > this._settleUntil || !this.isConnected) {
        this._settling = false;
        return;
      }
      const now = layoutSignature(this._controls());
      if (now !== this._signature) this._draw();
      setTimeout(check, 50);
    };
    setTimeout(check, 50);
  }

  _draw() {
    if (!this._config) return;
    const W = this._frame.clientWidth, H = this._frame.clientHeight;
    if (!W || !H) return;
    const p = this._prefix;
    const paint = resolveColor(this._config.paint_color, this, this._config.style === "none" ? "#bdbdbd" : "#1f6f78");
    const look = drawStyle(this._config, paint, p, W, H);
    const controls = this._controls();
    this._settle(layoutSignature(controls));
    const root = this.shadowRoot;

    // The features: on the style itself, on a flat patch of the style's base
    // (no rust, wear or splatter), or inset in a channel pressed into the
    // panel. The channel's corners are concentric with the feature's.
    const featuresStyle = look.theme ? "match" : this._config.features_style;
    this._frame.classList.toggle("styled", !look.theme);
    const inset = featuresStyle === "inset";
    const pad = inset ? 3 : 0;
    const areas = featuresStyle === "match" ? [] : controls.features.map((b) => {
      // A toggle rides close in its channel, like a magnet on a rail
      const gap = b.slide ? Math.min(pad, 1.5) : pad;
      return { x: b.x - gap, y: b.y - gap, w: b.w + 2 * gap, h: b.h + 2 * gap, radius: drawnRadius(b.radius + gap, b.w + 2 * gap, b.h + 2 * gap), slide: b.slide };
    });
    let texture = look.svg;
    if (areas.length && texture) {
      const holes = areas.map((b) => `<rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" rx="${b.radius}" fill="black" filter="url(#${p}edgeSoft)"/>`).join("");
      texture = `<defs><mask id="${p}clear"><rect width="100%" height="100%" fill="white"/>${holes}</mask></defs><g mask="url(#${p}clear)">${texture}</g>`;
    }
    root.getElementById("channels").innerHTML = !inset ? "" : areas.map((b) =>
      `<div class="channel${b.slide ? " rail" : ""}" style="left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px;border-radius:${b.radius}px"></div>`).join("");
    // Inset, the controls look physical: a slatted slider bar, color
    // favorites as keys, and the toggle as a slide
    // These style parts inside Home Assistant's controls; if that ever
    // fails, the controls keep their usual look and the card still draws
    try {
      for (const slider of controls.sliders) styleSlider(slider, inset);
      for (const swatch of controls.swatches) styleControl(swatch, "lampster-key", inset);
      for (const toggle of controls.switches) styleControl(toggle, "lampster-slide", inset);
      this._swatches = inset ? controls.swatches : [];
      this._markPressed();
    } catch (err) {
      console.warn("The Lampster card: could not style the controls", err);
    }
    root.getElementById("bg").style.background = look.bg;
    root.getElementById("texture").innerHTML = `<defs>${textureFilters(p, this._config.pattern)}</defs>${texture}`;
    root.getElementById("gloss").style.background = look.gloss ? GLOSS : "none";
    if (this._tile) {
      this._tile.classList.toggle("light", look.tone === "light");
      this._tile.classList.toggle("dark", look.tone === "dark");
    }

    // Fasteners: smaller on a single-row card; none is ever left out
    const { type: fasteners, color: fastenerColor } = this._config.fasteners;
    const { gaps: spacing, ends: atEnds } = parseSpacing(this._config.fasteners.spacing);
    let markup = "";
    if (fasteners !== "none") {
      const compact = H < 80;  // a single row
      // An inset takes room around the features: move the fasteners outward
      const edge = (compact ? 5 : 7) - (inset ? 1.5 : 0);
      const size = fasteners === "rivets" ? (compact ? 6.5 : 8) : (compact ? 7.5 : 9.5);
      const color = fastenerColor === "match" ? look.metal : resolveColor(fastenerColor, this, look.metal);
      const radius = drawnRadius(parseFloat(getComputedStyle(this._frame).borderTopLeftRadius) || 12, W, H);
      const points = fastenerPositions(spacing, W, H, radius, edge, compact && atEnds);
      markup = `<defs>${fastenerSymbols(p)}</defs>` +
        points
          .map(([x, y], i) =>
            `<use href="#${p}${fasteners}" color="${color}" x="${x - size / 2}" y="${y - size / 2}" width="${size}" height="${size}"` +
            ` transform="rotate(${fasteners === "rivets" ? 0 : (i * 37) % 90} ${x} ${y})"/>`).join("");
    }
    root.getElementById("fasteners").innerHTML = markup;

    // The head's housing follows the style
    if (this._housing !== look.housing) {
      this._housing = look.housing;
      if (this._hass && this._tile) this._tile.hass = this._innerHass(this._hass);
    }
  }
}

// ---------------------------------------------------------------------------
// The editor: the tile card's own editor, plus a panel for the style
// ---------------------------------------------------------------------------

// Tile card options this card sets itself, so they are left out of its editor
const HIDDEN_TILE_OPTIONS = ["icon", "show_entity_picture"];

function hideOptions(schema) {
  return schema
    .filter((item) => !HIDDEN_TILE_OPTIONS.includes(item.name))
    .map((item) => (Array.isArray(item.schema) ? { ...item, schema: hideOptions(item.schema) } : item));
}

/**
 * The tile card's editor, with the options above left out. It is the tile
 * card's own editor class, so it keeps every future change to it. It
 * filters the editor's form layout; if a Home Assistant update renames
 * that layout, the editor still works and simply shows those options again.
 */
function tileEditorType() {
  if (customElements.get(TILE_EDITOR_TYPE)) return TILE_EDITOR_TYPE;
  const Base = customElements.get("hui-tile-card-editor");
  if (!Base) return null;
  customElements.define(TILE_EDITOR_TYPE, class extends Base {
    constructor() {
      super();
      const original = this._schema;
      if (typeof original !== "function") return;
      let lastIn, lastOut;
      this._schema = (...args) => {
        const schema = original.apply(this, args);
        if (schema !== lastIn) {
          lastIn = schema;
          lastOut = Array.isArray(schema) ? hideOptions(schema) : schema;
        }
        return lastOut;
      };
    }
  });
  return TILE_EDITOR_TYPE;
}

const LABELS = {
  collection: "Collection",
  style: "Style",
  paint_color: "Paint color",
  // The fastener fields; they are saved under fasteners as color and spacing
  fastener_color: "Fastener color",
  fastener_spacing: "Fastener spacing",
  features_style: "Features style",
};

// A small picture of each fastener for the Fasteners choice
function fastenerPicture(kind) {
  const body = kind === "none"
    ? `<circle cx="6" cy="6" r="4.4" fill="none" stroke="#8a9096" stroke-width=".6" stroke-dasharray="1.2 1"/>`
    : `<defs>${fastenerSymbols("f")}</defs><use href="#f${kind}" color="#b9bfc5" width="12" height="12"/>`;
  return "data:image/svg+xml," + encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 12 12" width="40" height="40">${body}</svg>`);
}

const select = (options) => ({ select: { mode: "dropdown", options: options.map(([value, label]) => ({ value: String(value), label })) } });

class LampsterCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    // The panel matches the tile card editor's own sections
    this.shadowRoot.innerHTML = `
      <style>
        #tile { display: block; }
        ha-expansion-panel {
          display: block; margin-top: 24px;
          --expansion-panel-content-padding: 0;
          border-radius: var(--ha-border-radius-md, 8px);
          --ha-card-border-radius: var(--ha-border-radius-md, 8px);
        }
        ha-expansion-panel ha-svg-icon { color: var(--secondary-text-color); }
        ha-expansion-panel > [slot="header"] { margin: 0; font-size: inherit; font-weight: inherit; }
        .content { padding: 12px; }
        ha-form { display: block; }
        .row { display: flex; align-items: center; gap: 12px; margin: 24px 0; }
        .row ha-form { flex: 1; }
        .label { color: var(--primary-text-color); margin-bottom: 8px; }
        .choices { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 24px; }
        .choices button {
          width: 56px; height: 56px; padding: 0; display: grid; place-items: center; cursor: pointer;
          background: var(--card-background-color, transparent);
          border: 1px solid var(--outline-color, var(--divider-color)); border-radius: var(--ha-border-radius-md, 8px);
        }
        .choices button[aria-checked="true"] {
          border: 2px solid var(--primary-color);
          background: color-mix(in srgb, var(--primary-color) 12%, transparent);
        }
        .choices button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
        .choices img { width: 36px; height: 36px; pointer-events: none; }
      </style>
      <div id="tile"></div>
      <ha-expansion-panel outlined expanded>
        <ha-svg-icon slot="leading-icon" id="icon"></ha-svg-icon>
        <div slot="header" role="heading" aria-level="3">The Lampster Style</div>
        <div class="content">
          <ha-form id="look"></ha-form>
          <div class="row" id="row">
            <ha-button id="randomize"></ha-button>
            <ha-form id="controls"></ha-form>
          </div>
          <div class="label" id="fastenersLabel">Fasteners</div>
          <div class="choices" id="fastenerChoices" role="radiogroup" aria-labelledby="fastenersLabel"></div>
          <ha-form id="fasteners"></ha-form>
        </div>
      </ha-expansion-panel>`;
    this.shadowRoot.getElementById("icon").path = ICON;
    this._forms = ["look", "controls", "fasteners"].map((id) => this.shadowRoot.getElementById(id));
    for (const form of this._forms) {
      form.computeLabel = (schema) => schema.label ?? LABELS[schema.name] ?? schema.name;
      form.addEventListener("value-changed", (ev) => this._formChanged(ev));
    }
    // Fasteners: a picture of each, chosen like radio buttons
    const choices = this.shadowRoot.getElementById("fastenerChoices");
    for (const [value, label] of FASTENERS) {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "radio");
      button.title = label;
      button.setAttribute("aria-label", label);
      button.dataset.value = value;
      button.innerHTML = `<img alt="" src="${fastenerPicture(value)}">`;
      button.addEventListener("click", () => this._updateFasteners({ type: value }));
      choices.append(button);
    }
    choices.addEventListener("keydown", (ev) => {
      // Arrow keys move between the choices, like radio buttons
      const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
      if (!step) return;
      ev.preventDefault();
      const index = FASTENERS.findIndex(([value]) => value === validateForEditor(this._config).fasteners.type);
      const [value] = FASTENERS[(index + step + FASTENERS.length) % FASTENERS.length];
      this._updateFasteners({ type: value });
      choices.querySelector(`[data-value="${value}"]`).focus();
    });
    this.shadowRoot.getElementById("randomize").addEventListener("click", () => {
      this._update({ pattern: 1 + Math.floor(Math.random() * 99999) });
    });
  }

  set hass(hass) {
    this._hass = hass;
    for (const form of this._forms) form.hass = hass;
    if (this._tileEditor) this._tileEditor.hass = hass;
  }

  set lovelace(lovelace) {
    this._lovelace = lovelace;
    if (this._tileEditor) this._tileEditor.lovelace = lovelace;
  }

  // Called with every change, including edits in the YAML editor
  setConfig(config) {
    this._config = explicit(config);
    this._collection = undefined;
    this._render();
    this._setTileEditorConfig();
    // Options left out (defaults included) are written out, so the YAML
    // always shows what the card uses
    if (JSON.stringify(this._config) !== JSON.stringify(config)) this._fire();
  }

  async _setTileEditorConfig() {
    if (!this._tileEditor) {
      this._loading ??= (async () => {
        const helpers = await window.loadCardHelpers();
        helpers.createCardElement({ type: "tile", entity: this._config.entity });
        await customElements.whenDefined("hui-tile-card");
        const original = await customElements.get("hui-tile-card").getConfigElement();
        const type = tileEditorType();
        const editor = type ? document.createElement(type) : original;
        editor.addEventListener("config-changed", (ev) => {
          // The tile card's options changed: keep ours and pass the whole card on
          ev.stopPropagation();
          const own = Object.fromEntries(OWN_KEYS.filter((k) => k in this._config).map((k) => [k, this._config[k]]));
          const next = { ...ev.detail.config, ...own, type: this._config.type };
          delete next.show_entity_picture;  // always on: the head is shown there
          this._config = next;
          this._fire();
        });
        editor.hass = this._hass;
        if (this._lovelace) editor.lovelace = this._lovelace;
        this.shadowRoot.getElementById("tile").replaceWith(editor);
        this._tileEditor = editor;
      })();
      await this._loading;
    }
    this._tileEditor.setConfig(tileConfig(this._config));
  }

  _render() {
    const c = validateForEditor(this._config);
    const collection = COLLECTIONS.find((g) => g.id === (this._collection ?? collectionOf(c.style)));
    const [look, controls, fasteners] = this._forms;
    const none = c.style === "none";
    const collectionField = { name: "collection", selector: select(COLLECTIONS.map((g) => [g.id, g.name])) };
    look.schema = [
      none
        // The theme's own tile: only the head's color to choose
        ? { type: "grid", name: "", schema: [collectionField, { name: "paint_color", label: "Head color", selector: { ui_color: {} } }] }
        : { type: "grid", name: "", schema: [collectionField, { name: "style", selector: select(collection.styles) }] },
      ...(c.style === "painted" ? [{ name: "paint_color", selector: { ui_color: {} } }] : []),
    ];
    // Randomize and Features style do not apply to the theme's own tile
    this.shadowRoot.getElementById("row").style.display = none ? "none" : "";
    controls.schema = [{ name: "features_style", selector: select(FEATURES_STYLES) }];
    for (const button of this.shadowRoot.querySelectorAll("#fastenerChoices button")) {
      const checked = button.dataset.value === c.fasteners.type;
      button.setAttribute("aria-checked", String(checked));
      button.tabIndex = checked ? 0 : -1;
    }
    fasteners.schema = c.fasteners.type === "none" ? [] : [
      {
        type: "grid", name: "", schema: [
          { name: "fastener_spacing", selector: select(GAPS) },
          { name: "fastener_color", selector: { ui_color: { extra_options: [{ value: MATCH[0], label: MATCH[1] }] } } },
        ],
      },
    ];
    const data = {
      ...c, collection: collection.id,
      fastener_color: c.fasteners.color, fastener_spacing: String(parseSpacing(c.fasteners.spacing).gaps),
    };
    for (const form of this._forms) form.data = data;

    // Every style but Brushed Aluminum has something to randomize
    const what = RANDOMIZED(c.style);
    const button = this.shadowRoot.getElementById("randomize");
    button.disabled = !what;
    button.textContent = what ? `Randomize ${what}` : "Nothing to randomize";
  }

  _formChanged(ev) {
    ev.stopPropagation();
    const value = ev.detail.value;
    const c = validateForEditor(this._config);
    if (value.collection !== collectionOf(c.style) && value.style === c.style) {
      // A new collection: start on its first style
      this._collection = value.collection;
      this._update({ style: COLLECTIONS.find((g) => g.id === value.collection).styles[0][0] });
      return;
    }
    this._collection = undefined;
    const changes = {};
    for (const key of ["style", "paint_color", "features_style"]) {
      if (key in value && JSON.stringify(value[key]) !== JSON.stringify(c[key])) changes[key] = value[key];
    }
    // The fastener fields go into the fasteners group; the spacing keeps an
    // E set in the YAML (ends on single-row cards)
    const fasteners = {};
    if ("fastener_color" in value && value.fastener_color !== c.fasteners.color) fasteners.color = value.fastener_color;
    const spacing = parseSpacing(c.fasteners.spacing);
    if ("fastener_spacing" in value && value.fastener_spacing !== String(spacing.gaps)) {
      fasteners.spacing = parseSpacing(`${value.fastener_spacing}${spacing.ends ? "E" : ""}`)?.value;
    }
    if (Object.keys(fasteners).length) changes.fasteners = { ...this._config.fasteners, ...fasteners };
    if (Object.keys(changes).length) this._update(changes);
  }

  _updateFasteners(changes) {
    this._update({ fasteners: { ...this._config.fasteners, ...changes } });
  }

  _update(changes) {
    this._config = explicit({ ...this._config, ...changes });
    this._render();
    this._fire();
  }

  _fire() {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
  }
}

/**
 * The configuration as the editor saves it: every option the chosen style
 * uses written out, defaults included (so "match" appears in the YAML), and
 * the options it does not use removed:
 * - paint_color only for Painted and None,
 * - pattern only for styles with something to randomize,
 * - features_style for every style but None,
 * - fasteners color and spacing unless the type is none,
 * - options of earlier versions of the card.
 */
function explicit(config) {
  const c = { ...config };
  for (const key of RETIRED_KEYS) delete c[key];
  const style = STYLES[c.style] ? c.style : DEFAULTS.style;
  c.style = style;
  if (usesPaint(style)) c.paint_color ??= DEFAULT_PAINT[style];
  else delete c.paint_color;
  if (!RANDOMIZED(style)) delete c.pattern;
  if (style === "none") delete c.features_style;
  else c.features_style ??= DEFAULTS.features_style;
  const given = c.fasteners && typeof c.fasteners === "object" && !Array.isArray(c.fasteners) ? c.fasteners : {};
  const type = given.type ?? FASTENER_DEFAULTS.type;
  c.fasteners = type === "none"
    ? { type }
    : { type, color: given.color ?? FASTENER_DEFAULTS.color, spacing: given.spacing ?? FASTENER_DEFAULTS.spacing };
  return c;
}

// The editor shows what the card would draw, without failing on a half-typed YAML value
function validateForEditor(config) {
  try {
    return validate({ entity: "-", ...config });
  } catch (err) {
    const c = { ...DEFAULTS, ...explicit(config) };
    if (!FEATURES_STYLES.some(([id]) => id === c.features_style)) c.features_style = DEFAULTS.features_style;
    if (!FASTENERS.some(([id]) => id === c.fasteners.type)) c.fasteners.type = FASTENER_DEFAULTS.type;
    c.fasteners.color ??= FASTENER_DEFAULTS.color;
    c.fasteners.spacing = parseSpacing(c.fasteners.spacing ?? FASTENER_DEFAULTS.spacing)?.value ?? FASTENER_DEFAULTS.spacing;
    return c;
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, LampsterCard);
  customElements.define(EDITOR_TYPE, LampsterCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TYPE,
    name: "The Lampster",
    description: "A tile card for The Lampster, in a metal or Lampster finish with fasteners.",
    preview: true,
    documentationURL: "https://github.com/yamanote1138/lampster-ha-integration#dashboard-card",
  });
  console.info(`%c THE LAMPSTER CARD %c ${VERSION} `, "color: #fff; background: #555; font-weight: bold", "color: #fff; background: #e0201b");
}
