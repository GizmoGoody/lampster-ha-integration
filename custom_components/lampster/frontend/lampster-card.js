/**
 * The Lampster card: a tile card dressed in a metal or Lampster finish.
 *
 * The card wraps Home Assistant's own tile card, so the layout, actions,
 * features and more-info dialog are exactly the tile card's. It only adds:
 * - a style (finish) drawn behind the tile card,
 * - fasteners drawn on top of it, and
 * - a picture of The Lampster's head in place of the tile card's icon, shown
 *   through the tile card's own "show entity picture" option. The light's
 *   color fills the lens. The picture is built in memory; no files are written.
 *
 * Every tile card option works the same way here. The card's own options:
 *   style, paint_color, pattern, fasteners, fastener_color,
 *   fastener_custom_color, fastener_spacing
 */

const CARD_TYPE = "lampster-card";
const EDITOR_TYPE = "lampster-card-editor";
const VERSION = "1.0.0";

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
// Styles whose rust, wear or splatter is drawn from the pattern number
const PATTERNED = (style) => style === "rusted" || /^(army|artsy)_/.test(style);

const FASTENERS = [["rivets", "Rivets"], ["phillips", "Phillips"], ["hex", "Hex"], ["socket", "Socket"], ["none", "None"]];
const FASTENER_COLORS = [["match", "Match"], ["custom", "Custom"]];
// Fastener spacing: the number is how many gaps each long edge is divided into
const SPACINGS = [[0, "Corners"], [2, "Half"], [4, "Quarter"], [8, "Eighth"], [16, "Sixteenth"], [32, "Thirty-second"], [64, "Sixty-fourth"]];

const DEFAULTS = {
  style: "polished",
  paint_color: [31, 111, 120],
  pattern: 17,
  fasteners: "rivets",
  fastener_color: "match",
  fastener_custom_color: [212, 175, 55],
  fastener_spacing: 4,
};
const OWN_KEYS = Object.keys(DEFAULTS);

function validate(config) {
  if (!config.entity) throw new Error("Specify an entity");
  const c = { ...DEFAULTS, ...config };
  if (!STYLES[c.style]) throw new Error(`Unknown style: ${c.style}`);
  if (!FASTENERS.some(([id]) => id === c.fasteners)) throw new Error(`Unknown fasteners: ${c.fasteners}`);
  if (!FASTENER_COLORS.some(([id]) => id === c.fastener_color)) throw new Error(`fastener_color must be match or custom`);
  c.fastener_spacing = Number(c.fastener_spacing);
  if (!SPACINGS.some(([n]) => n === c.fastener_spacing)) {
    throw new Error(`fastener_spacing must be one of ${SPACINGS.map(([n]) => n).join(", ")}`);
  }
  for (const key of ["paint_color", "fastener_custom_color"]) {
    if (!Array.isArray(c[key]) || c[key].length !== 3) throw new Error(`${key} must be [red, green, blue]`);
  }
  c.pattern = Math.abs(Math.round(Number(c.pattern))) || DEFAULTS.pattern;
  return c;
}

// The tile card's part of the configuration
function tileConfig(config) {
  const tile = { ...config, type: "tile", show_entity_picture: true };
  for (const key of OWN_KEYS) delete tile[key];
  return tile;
}

// ---------------------------------------------------------------------------
// Drawing
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
// Seeded random, so a pattern number always draws the same pattern
const rng = (seed) => () => (seed = (seed * 16807 + 1) % 2147483647) / 2147483647;

const GLOSS = "linear-gradient(160deg, rgba(255,255,255,0) 12%, rgba(255,255,255,.24) 45%, rgba(255,255,255,0) 78%)";
const POLISH = "linear-gradient(115deg, rgba(255,255,255,0) 8%, rgba(255,255,255,.5) 42%, rgba(255,255,255,0) 76%)";
const POLISH_SOFT = "linear-gradient(115deg, rgba(255,255,255,0) 8%, rgba(255,255,255,.28) 42%, rgba(255,255,255,0) 76%)";
const ALUMINUM = "linear-gradient(180deg, #aeb3b7 0%, #92989d 45%, #a6abb0 70%, #868c92 100%)";
const POLISHED = [
  "linear-gradient(100deg, rgba(0,0,0,.28) 0%, rgba(0,0,0,0) 12%, rgba(255,255,255,.7) 27%, rgba(255,255,255,0) 42%, rgba(0,0,0,.32) 54%, rgba(0,0,0,0) 64%, rgba(255,255,255,.5) 77%, rgba(255,255,255,0) 90%, rgba(0,0,0,.25) 100%)",
  "linear-gradient(180deg, rgba(255,255,255,.25) 0%, rgba(255,255,255,0) 35%, rgba(0,0,0,0) 70%, rgba(0,0,0,.25) 100%)",
  "linear-gradient(180deg, #9ea3a7, #8c9196)",
].join(", ");

// Noise textures shared by the styles; "p" is a prefix that keeps the ids unique per card
function textureFilters(p) {
  const noise = (id, freq, octaves, seed, matrix, srgb = false) =>
    `<filter id="${p}${id}" x="0" y="0" width="100%" height="100%"${srgb ? ' color-interpolation-filters="sRGB"' : ""}>` +
    `<feTurbulence type="fractalNoise" baseFrequency="${freq}" numOctaves="${octaves}" seed="${seed}"/>` +
    `<feColorMatrix values="${matrix}"/></filter>`;
  return [
    noise("mottle", "0.012 0.03", 3, 4, "0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .22 0"),
    noise("mottleDark", "0.008 0.02", 3, 12, "0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .3 -.05"),
    noise("matte", "0.9", 2, 3, "0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .16 0"),
    noise("matteDark", "0.7", 2, 8, "0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .14 0"),
    noise("rustBlotch", "0.018 0.03", 5, 11, "0 0 0 0 .7  0 0 0 0 .32  0 0 0 0 .11  0 0 0 3 -1.25", true),
    noise("rustScale", "0.05", 5, 21, "0 0 0 0 .22  0 0 0 0 .09  0 0 0 0 .04  0 0 0 6 -3.2", true),
    noise("rustGrain", "0.8", 1, 6, "0 0 0 0 .78  0 0 0 0 .38  0 0 0 0 .14  0 0 0 2.5 -1.4", true),
    noise("rustPits", "0.4", 2, 2, "0 0 0 0 .12  0 0 0 0 .04  0 0 0 0 .02  0 0 0 6 -3.5", true),
    `<filter id="${p}soft"><feGaussianBlur stdDeviation="6"/></filter>`,
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
 * What a style looks like: background CSS, an SVG overlay, whether it gets
 * the gloss, the head's housing color, the matching fastener color, and
 * whether its text should be dark ("light" style) or light ("dark" style).
 */
function drawStyle(config, p, W, H) {
  const { style, pattern: seed } = config;
  const rect = (attrs) => `<rect width="100%" height="100%" ${attrs}/>`;
  const tone = (color) => (luma(color) > 0.6 ? "light" : "dark");
  if (style === "polished") {
    return { bg: POLISHED, svg: rect(`filter="url(#${p}mottle)"`) + rect(`filter="url(#${p}mottleDark)"`), housing: "#b4b9be", metal: "#c3c8cc", tone: "light" };
  }
  if (style === "brushed") {
    return {
      bg: `${POLISH}, radial-gradient(120% 140% at 30% 0%, #c9cdd1 0%, #b3b8bd 50%, #9da3a9 100%)`,
      svg: rect(`filter="url(#${p}matte)"`) + rect(`filter="url(#${p}matteDark)"`),
      housing: "#aeb3b8", metal: "#b8bdc2", tone: "light",
    };
  }
  if (style === "painted") {
    const paint = hex(config.paint_color);
    return { bg: `${POLISH}, linear-gradient(180deg, ${shade(paint, 1.3)}, ${paint} 55%, ${shade(paint, 0.72)})`, svg: "", housing: paint, metal: paint, tone: tone(paint) };
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
    const paint = COLOR[c];
    return { bg: `${GLOSS}, linear-gradient(180deg, ${shade(paint, 1.25)}, ${paint} 50%, ${shade(paint, 0.65)})`, svg: "", housing: paint, metal: paint, tone: tone(paint) };
  }
  if (group === "artsy") {  // paint splatter
    const paint = ARTSY[c];
    return {
      bg: `linear-gradient(180deg, ${shade(paint, 1.15)}, ${paint} 55%, ${shade(paint, 0.8)})`,
      svg: splatter(SPLATTER[c], W, H, seed + c.length), gloss: true, housing: paint, metal: paint, tone: tone(paint),
    };
  }
  // Army: worn paint showing rust (near-black on Army Red) in patches and
  // along the edges, and a stenciled star
  const paint = ARMY[c];
  const star = c === "white" ? "#a3261c" : "#e9e9e6";
  const wear = c === "red" ? "0 0 0 0 .02  0 0 0 0 .015  0 0 0 0 .012" : "0 0 0 0 .42  0 0 0 0 .2  0 0 0 0 .07";
  const edge = c === "red" ? "0 0 0 0 .02  0 0 0 0 .015  0 0 0 0 .012" : "0 0 0 0 .38  0 0 0 0 .18  0 0 0 0 .06";
  const sx = W - 52, sy = Math.min(46, H / 2);
  const points = Array.from({ length: 10 }, (_, i) => {
    const a = -Math.PI / 2 + (i * Math.PI) / 5, r = i % 2 ? 7 : 17;
    return `${(sx + r * Math.cos(a)).toFixed(1)},${(sy + r * Math.sin(a)).toFixed(1)}`;
  }).join(" ");
  return {
    bg: `linear-gradient(180deg, ${shade(paint, 1.08)}, ${paint} 60%, ${shade(paint, 0.82)})`,
    svg: `<defs>
            <filter id="${p}wear" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.045 0.06" numOctaves="4" seed="${seed}"/><feColorMatrix values="${wear}  0 0 0 -14 4.6"/></filter>
            <filter id="${p}edge" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="3" seed="${seed + 50}"/><feColorMatrix values="${edge}  0 0 0 -10 4.3"/></filter>
            <mask id="${p}edgeMask">${rect('fill="white"')}<rect x="16" y="14" width="${Math.max(0, W - 32)}" height="${Math.max(0, H - 28)}" rx="8" fill="black" filter="url(#${p}soft)"/></mask>
          </defs>
          <polygon points="${points}" fill="${star}" opacity=".85"/>
          ${rect(`filter="url(#${p}wear)"`)}
          ${rect(`filter="url(#${p}edge)" mask="url(#${p}edgeMask)"`)}`,
    gloss: true, housing: paint, metal: paint, tone: tone(paint),
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
 * Where the fasteners go. Every fastener is the same distance from its
 * nearest edge; the corner ones are measured from the rounded corner.
 * Spacing 0 is corners only; otherwise each long edge is divided into
 * "spacing" gaps, and each short edge is halved again whenever the long-edge
 * gap is at most half of the short edge's current gap.
 */
const INSET = 8;
function fastenerPositions(spacing, W, H, radius) {
  const c = radius - (radius - INSET) / Math.SQRT2;
  const points = [[c, c], [W - c, c], [c, H - c], [W - c, H - c]];
  if (!spacing) return points;
  const wide = W >= H;
  const long = wide ? W : H, short = wide ? H : W;
  const L = long - 2 * c, S = short - 2 * c, gap = L / spacing;
  let shortParts = 1;
  while (gap <= S / (shortParts * 2)) shortParts *= 2;
  const add = (a, b) => points.push(wide ? [a, b] : [b, a]);
  for (let i = 1; i < spacing; i++) {
    add(c + i * gap, INSET);
    add(c + i * gap, short - INSET);
  }
  for (let i = 1; i < shortParts; i++) {
    add(INSET, c + (i * S) / shortParts);
    add(long - INSET, c + (i * S) / shortParts);
  }
  return points;
}

// The Lampster head, from the integration's icon: housing outline, top ridge,
// lens opening and the three screws
const HEAD_OUTLINE = "M21.9903,11.5386c-.0826.3308-.2558.602-.2984.8878v.1504c0,5.2044-4.3393,9.4232-9.6919,9.4232S2.3081,17.7812,2.3081,12.5768c0-.0502.0007-.1504.0007-.1504-.0426-.2858-.2165-.557-.2991-.8878-.0173-.0688-.0092-.2314.0062-.3008.6008-2.691,1.2682-5.4358,1.444-6.0864.4098-1.228,2.0337-2.9294,3.8746-3.064,2.2063-.055,3.9833-.0874,4.6655-.0874s2.4592.0324,4.6655.0874c1.8409.1346,3.4648,1.836,3.8746,3.064.1757.6506.8431,3.3954,1.444,6.0864.0155.0694.0235.232.0062.3008Z";
const HEAD_RIDGE = "M21.2352,11.1522c-.3024-1.4878-.6706-3.1298-1.094-4.8802l-.0276-.1132c-.0476-.194-.0966-.3946-.1496-.5932-.0018-.0064-.0038-.0128-.006-.019-.0658-.184-.1554-.3692-.2664-.5502-.0006-.001-.0012-.002-.0018-.003-.3246-.5132-.7522-.9748-1.2366-1.3346-.5164-.3838-1.0926-.646-1.6666-.7584-.0028-.0006-.0058-.0012-.0086-.0016l-.1402-.0222c-.004-.0006-.008-.0012-.012-.0016l-.145-.0154c-.006-.0006-.012-.001-.018-.0012-.754-.023-1.55-.04-2.3018-.049-.8346-.0072-1.5756-.0108-2.2664-.0108-1.5586,0-2.939.0182-4.2202.0558h-.001c-.0154.0004-.0308.0008-.0462.0012-.0304.0008-.062.0016-.095.0034-.0044.0002-.0086.0006-.013.001,0,0-.1298.0138-.1434.0152-.0034.0004-.007.0008-.0104.0012-.9906.143-1.9546.7256-2.7142,1.6404-.0006.0008-.0014.0016-.002.0024-.2956.3652-.4894.6944-.6096,1.036-.0024.007-.0046.014-.0064.021-.4576,1.814-1.2598,5.5358-1.2678,5.5732-.0274.1274.0518.2534.1784.2838.0188.0046.0378.0068.0564.0068.1064,0,.2032-.0712.2318-.1782.1124-.4228.2394-.9042.3738-1.414.3656-1.3874.78-2.9592,1.0952-4.0684.4254-1.04,1.8198-1.9512,2.992-1.953h.004c1.1432-.0208,2.4286-.0306,4.0454-.0306.8112,0,1.6238.0024,2.4096.0046h.0024c.7114.0048,1.497.0148,2.2716.029l.108.0104c.0582.0086.0918.0136.1126.0164v.0002c1.0414.189,1.9322.7426,2.444,1.5188.0772.1188.1642.2862.2048.394.091.3144.2174.7716.3754,1.359.2472.919.8648,3.2486,1.097,4.1328.0284.1074.1254.179.232.179.018,0,.0364-.002.0546-.0062.1266-.0296.2066-.1544.1808-.2816Z";
const HEAD_LENS = "M12.015,4.9077c-4.1974,0-7.6,3.4026-7.6,7.6s3.4026,7.6,7.6,7.6,7.6-3.4026,7.6-7.6-3.4026-7.6-7.6-7.6Z";
const HEAD_SCREWS = "M11.6614,20.5264c-.1953.1953-.1953.5118,0,.7071s.5118.1953.7071,0,.1953-.5118,0-.7071-.5118-.1953-.7071,0ZM19.1362,8.8045c.2667.0715.5409-.0868.6124-.3536s-.0868-.5409-.3536-.6124-.5409.0868-.6124.3536.0868.5409.3536.6124ZM5.2473,8.1921c-.0715-.2667-.3456-.425-.6124-.3536s-.425.3456-.3536.6124.3456.425.6124.3536.425-.3456.3536-.6124Z";

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
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0, 0, 0, .35));
        }
        .layer { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
        .tile {
          position: relative; display: block; height: 100%;
          --ha-card-background: transparent; --card-background-color: transparent;
          --ha-card-box-shadow: none; --ha-card-border-width: 0; --ha-card-border-color: transparent;
          --ha-tile-icon-border-radius: 0;
        }
        .tile.light { --primary-text-color: #1d2126; --secondary-text-color: #3c434b; text-shadow: 0 1px 0 rgba(255, 255, 255, .5); }
        .tile.dark { --primary-text-color: #f4f4f4; --secondary-text-color: #dadada; text-shadow: 0 1px 2px rgba(0, 0, 0, .8); }
        #fasteners { z-index: 1; }
      </style>
      <div class="frame">
        <div class="layer" id="bg"></div>
        <svg class="layer" id="texture"></svg>
        <div class="layer" id="gloss"></div>
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
    return { entity, features: [{ type: "light-brightness" }], style: DEFAULTS.style, fasteners: DEFAULTS.fasteners, fastener_spacing: DEFAULTS.fastener_spacing };
  }

  setConfig(config) {
    this._config = validate(config);
    const tile = tileConfig(config);
    if (this._tile) {
      this._tile.setConfig(tile);
    } else if (customElements.get("hui-tile-card")) {
      this._createTile(tile);
    } else {
      // The tile card is loaded on demand; the card helpers load it
      window.loadCardHelpers?.().then(async (helpers) => {
        if (this._tile) return;
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
    this._frame.insertBefore(this._tile, this.shadowRoot.getElementById("fasteners"));
    this._draw();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._tile) this._tile.hass = this._innerHass(hass);
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

  _draw() {
    if (!this._config) return;
    const W = this._frame.clientWidth, H = this._frame.clientHeight;
    if (!W || !H) return;
    const p = this._prefix;
    const look = drawStyle(this._config, p, W, H);
    const root = this.shadowRoot;
    root.getElementById("bg").style.background = look.bg;
    root.getElementById("texture").innerHTML = `<defs>${textureFilters(p)}</defs>${look.svg}`;
    root.getElementById("gloss").style.background = look.gloss ? GLOSS : "none";
    if (this._tile) {
      this._tile.classList.toggle("light", look.tone === "light");
      this._tile.classList.toggle("dark", look.tone === "dark");
    }

    const { fasteners, fastener_spacing: spacing } = this._config;
    const color = this._config.fastener_color === "custom" ? hex(this._config.fastener_custom_color) : look.metal;
    const radius = parseFloat(getComputedStyle(this._frame).borderTopLeftRadius) || 12;
    const size = fasteners === "rivets" ? 9 : 11;
    root.getElementById("fasteners").innerHTML = fasteners === "none" ? "" :
      `<defs>${fastenerSymbols(p)}</defs>` +
      fastenerPositions(spacing, W, H, radius).map(([x, y], i) =>
        `<use href="#${p}${fasteners}" color="${color}" x="${x - size / 2}" y="${y - size / 2}" width="${size}" height="${size}"` +
        ` transform="rotate(${fasteners === "rivets" ? 0 : (i * 37) % 90} ${x} ${y})"/>`).join("");

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

const LABELS = {
  collection: "Collection",
  style: "Style",
  paint_color: "Paint color",
  fasteners: "Fasteners",
  fastener_color: "Fastener color",
  fastener_custom_color: "Custom fastener color",
  fastener_spacing: "Fastener spacing",
};

const select = (options) => ({ select: { mode: "dropdown", options: options.map(([value, label]) => ({ value: String(value), label })) } });

class LampsterCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        .tile-editor { display: block; }
        ha-expansion-panel { display: block; margin-top: 24px; }
        .content { padding: 12px 0 4px; }
        .pattern { display: flex; align-items: center; gap: 12px; margin-top: 16px; }
        .pattern span { color: var(--secondary-text-color); font-size: 14px; }
      </style>
      <div id="tile"></div>
      <ha-expansion-panel outlined expanded>
        <ha-icon slot="leading-icon" icon="mdi:palette-swatch"></ha-icon>
        <h3 slot="header">The Lampster style</h3>
        <div class="content">
          <ha-form id="form"></ha-form>
          <div class="pattern" id="patternRow">
            <ha-button id="randomize"></ha-button>
            <span id="patternText"></span>
          </div>
        </div>
      </ha-expansion-panel>`;
    this._form = this.shadowRoot.getElementById("form");
    this._form.computeLabel = (schema) => LABELS[schema.name] ?? schema.name;
    this._form.addEventListener("value-changed", (ev) => this._formChanged(ev));
    this.shadowRoot.getElementById("randomize").addEventListener("click", () => {
      this._update({ pattern: 1 + Math.floor(Math.random() * 99999) });
    });
  }

  set hass(hass) {
    this._hass = hass;
    this._form.hass = hass;
    if (this._tileEditor) this._tileEditor.hass = hass;
  }

  set lovelace(lovelace) {
    this._lovelace = lovelace;
    if (this._tileEditor) this._tileEditor.lovelace = lovelace;
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
    this._setTileEditorConfig();
  }

  async _setTileEditorConfig() {
    if (!this._tileEditor) {
      if (!this._loading) {
        this._loading = (async () => {
          const helpers = await window.loadCardHelpers();
          helpers.createCardElement({ type: "tile", entity: this._config.entity });
          await customElements.whenDefined("hui-tile-card");
          const editor = await customElements.get("hui-tile-card").getConfigElement();
          editor.classList.add("tile-editor");
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
      }
      await this._loading;
    }
    this._tileEditor.setConfig(tileConfig(this._config));
  }

  _render() {
    const c = { ...DEFAULTS, ...this._config };
    const collection = COLLECTIONS.find((g) => g.id === (this._collection ?? collectionOf(c.style)));
    const schema = [
      {
        type: "grid", name: "", schema: [
          { name: "collection", selector: select(COLLECTIONS.map((g) => [g.id, g.name])) },
          { name: "style", selector: select(collection.styles) },
        ],
      },
      ...(c.style === "painted" ? [{ name: "paint_color", selector: { color_rgb: {} } }] : []),
      {
        type: "grid", name: "", schema: [
          { name: "fasteners", selector: select(FASTENERS) },
          { name: "fastener_spacing", selector: select(SPACINGS) },
        ],
      },
      ...(c.fasteners === "none" ? [] : [{ name: "fastener_color", selector: select(FASTENER_COLORS) }]),
      ...(c.fasteners !== "none" && c.fastener_color === "custom" ? [{ name: "fastener_custom_color", selector: { color_rgb: {} } }] : []),
    ];
    this._form.schema = schema;
    this._form.data = { ...c, collection: collection.id, fastener_spacing: String(c.fastener_spacing) };

    const patterned = PATTERNED(c.style);
    this.shadowRoot.getElementById("patternRow").style.display = patterned ? "" : "none";
    if (patterned) {
      const what = c.style === "rusted" ? "rust" : c.style.startsWith("army") ? "wear" : "splatter";
      this.shadowRoot.getElementById("randomize").textContent = `Randomize ${what}`;
      this.shadowRoot.getElementById("patternText").textContent = `Pattern ${c.pattern}`;
    }
  }

  _formChanged(ev) {
    ev.stopPropagation();
    const value = ev.detail.value;
    const c = { ...DEFAULTS, ...this._config };
    if (value.collection !== collectionOf(c.style) && value.style === c.style) {
      // A new collection: start on its first style
      this._collection = value.collection;
      const first = COLLECTIONS.find((g) => g.id === value.collection).styles[0][0];
      this._update({ style: first });
      return;
    }
    this._collection = undefined;
    const changes = {};
    for (const key of OWN_KEYS) {
      if (!(key in value)) continue;
      const next = key === "fastener_spacing" ? Number(value[key]) : value[key];
      if (JSON.stringify(next) !== JSON.stringify(c[key])) changes[key] = next;
    }
    if (Object.keys(changes).length) this._update(changes);
  }

  _update(changes) {
    this._config = { ...this._config, ...changes };
    this._render();
    this._fire();
  }

  _fire() {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
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
