const $ = (id) => document.getElementById(id);

const DEFAULT_LAYOUT = {
  reference_resolution: { w: 2560, h: 1440 },
  safezones: {
    match: {
      stats: {
        size: { w: 422, h: 447 },
        position: { x: 0, y: 802 },
      },
    },
    menu: {
      stats: {
        size: { w: 684, h: 102 },
        position: { x: 1192, y: 1238 },
      },
    },
  },
  scoreboard_layouts: {},
};
const DEFAULT_STATS_RECTS = {
  match: { x: 0, y: 802, w: 422, h: 447 },
  menu: { x: 1192, y: 1238, w: 684, h: 102 },
};

const fields = {
  statsSafezone: $("statsSafezone"),
  statsHud: $("statsHud"),
  feedStatus: $("feedStatus"),
};

let previousState = "";
let currentLayoutMode = "menu";
let overlayLayout = DEFAULT_LAYOUT;

function isRecord(value) {
  return value !== null && typeof value === "object";
}

function valueAt(source, path, fallback = "") {
  let current = source;
  for (const key of path) {
    if (!isRecord(current) || !(key in current)) {
      return fallback;
    }
    current = current[key];
  }
  return current ?? fallback;
}

function setText(element, value) {
  const text = String(value ?? "");
  if (!element) {
    return;
  }
  if (element.textContent !== text) {
    element.textContent = text;
  }
}

function setValue(name, value) {
  for (const element of document.querySelectorAll(`[data-value="${name}"]`)) {
    setText(element, value);
  }
}

function setFeedStatus(message) {
  setText(fields.feedStatus, message);
  fields.feedStatus.hidden = !message;
}

function toFiniteNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function formatWinRate(wins, losses) {
  const total = wins + losses;
  if (total <= 0) {
    return "0.00";
  }
  return ((wins / total) * 100).toFixed(2);
}

function formatWinLossRatio(wins, losses) {
  if (losses <= 0) {
    return wins > 0 ? wins.toFixed(1) : "0.0";
  }
  return (wins / losses).toFixed(1);
}

function formatKillDeathRatio(kills, deaths) {
  if (deaths <= 0) {
    return kills > 0 ? kills.toFixed(1) : "0.0";
  }
  return (kills / deaths).toFixed(1);
}

function formatStreak(value) {
  const text = String(value ?? "").trim();
  const match = /^([WL])(\d+)$/i.exec(text);
  if (!match) {
    return text || "0";
  }
  const sign = match[1].toUpperCase() === "W" ? "+" : "-";
  return `${sign}${match[2]}`;
}

function formatAverage(total, matches) {
  if (matches <= 0) {
    return "0";
  }
  const average = total / matches;
  return average >= 10 ? average.toFixed(0) : average.toFixed(1).replace(/\.0$/, "");
}

function formatSpeedNumber(value) {
  const text = String(value ?? "").trim();
  const match = /-?\d+(?:\.\d+)?/.exec(text);
  return match ? match[0] : "--";
}

function statsSafezoneSpec(layoutMode) {
  const modeStats = valueAt(overlayLayout, ["safezones", layoutMode, "stats"], null);
  if (isRecord(modeStats)) {
    return modeStats;
  }
  const rootStats = valueAt(overlayLayout, ["safezones", "stats"], null);
  if (isRecord(rootStats)) {
    return rootStats;
  }
  const fallbackMode = layoutMode === "match" ? "match" : "menu";
  return valueAt(
    overlayLayout,
    ["safezones", fallbackMode, "stats"],
    valueAt(DEFAULT_LAYOUT, ["safezones", fallbackMode, "stats"]),
  );
}

function statsSafezoneRect(layoutMode) {
  const fallback = DEFAULT_STATS_RECTS[layoutMode] ?? DEFAULT_STATS_RECTS.menu;
  const spec = statsSafezoneSpec(layoutMode);
  const rect = {
    x: toFiniteNumber(valueAt(spec, ["position", "x"], fallback.x), fallback.x),
    y: toFiniteNumber(valueAt(spec, ["position", "y"], fallback.y), fallback.y),
    w: toFiniteNumber(valueAt(spec, ["size", "w"], fallback.w), fallback.w),
    h: toFiniteNumber(valueAt(spec, ["size", "h"], fallback.h), fallback.h),
  };

  if (rect.w <= 0 || rect.h <= 0) {
    return { ...fallback };
  }
  return rect;
}

function safezoneReferenceBounds(value, bounds = { w: 0, h: 0 }) {
  if (Array.isArray(value)) {
    for (const child of value) {
      safezoneReferenceBounds(child, bounds);
    }
    return bounds;
  }

  if (!isRecord(value)) {
    return bounds;
  }

  const position = value.position;
  const size = value.size;
  if (isRecord(position) && isRecord(size)) {
    const x = toFiniteNumber(position.x, NaN);
    const y = toFiniteNumber(position.y, NaN);
    const w = toFiniteNumber(size.w, NaN);
    const h = toFiniteNumber(size.h, NaN);
    if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(w) && Number.isFinite(h)) {
      bounds.w = Math.max(bounds.w, x + w);
      bounds.h = Math.max(bounds.h, y + h);
    }
  }

  for (const child of Object.values(value)) {
    safezoneReferenceBounds(child, bounds);
  }
  return bounds;
}

function referenceResolution() {
  const reference = valueAt(overlayLayout, ["reference_resolution"], DEFAULT_LAYOUT.reference_resolution);
  const inferred = safezoneReferenceBounds(valueAt(overlayLayout, ["safezones"], DEFAULT_LAYOUT.safezones));
  return {
    w: Math.max(1, DEFAULT_LAYOUT.reference_resolution.w, inferred.w, toFiniteNumber(reference.w, 0)),
    h: Math.max(1, DEFAULT_LAYOUT.reference_resolution.h, inferred.h, toFiniteNumber(reference.h, 0)),
  };
}

function applyStatsSafezone(layoutMode = currentLayoutMode) {
  currentLayoutMode = layoutMode === "match" ? "match" : "menu";
  const rect = statsSafezoneRect(currentLayoutMode);
  const reference = referenceResolution();
  const scaleX = window.innerWidth / reference.w;
  const scaleY = window.innerHeight / reference.h;

  fields.statsSafezone.dataset.layout = currentLayoutMode;
  fields.statsSafezone.style.left = `${rect.x * scaleX}px`;
  fields.statsSafezone.style.top = `${rect.y * scaleY}px`;
  fields.statsSafezone.style.width = `${rect.w * scaleX}px`;
  fields.statsSafezone.style.height = `${rect.h * scaleY}px`;
  fields.statsSafezone.dataset.safezoneRect = `${rect.x},${rect.y},${rect.w},${rect.h}`;
  fields.statsSafezone.dataset.referenceResolution = `${reference.w}x${reference.h}`;
}

function layoutModeForState(state) {
  const mode = valueAt(state, ["context", "mode"], "");
  if (mode === "match" || mode === "freeplay") {
    return "match";
  }
  return "menu";
}

function render(state) {
  setFeedStatus("");
  fields.statsSafezone.hidden = false;
  applyStatsSafezone(layoutModeForState(state));

  const wins = toFiniteNumber(valueAt(state, ["session", "wins"], 0), 0);
  const losses = toFiniteNumber(valueAt(state, ["session", "losses"], 0), 0);
  const completedMatches = wins + losses;

  setValue("sessionWinRate", formatWinRate(wins, losses));
  setValue("sessionWins", wins);
  setValue("sessionLosses", losses);
  setValue("sessionStreak", formatStreak(valueAt(state, ["session", "streak"], 0)));
  setValue("sessionWinLossRatio", formatWinLossRatio(wins, losses));
  setValue("lastGoalSpeedNumber", formatSpeedNumber(valueAt(state, ["match", "last_goal_speed"], "-- kph")));

  const stats = [
    ["Goals", "goals"],
    ["Assists", "assists"],
    ["Saves", "saves"],
    ["Demos", "demos"],
    ["Deaths", "deaths"],
    ["HighFives", "high_fives"],
    ["LowFives", "low_fives"],
  ];

  for (const [label, key] of stats) {
    const matchValue = toFiniteNumber(valueAt(state, ["match", "stats", key], 0), 0);
    const sessionValue = toFiniteNumber(valueAt(state, ["session", key], 0), 0);
    setValue(`match${label}`, matchValue);
    setValue(`session${label}`, sessionValue);
    setValue(`avg${label}`, formatAverage(sessionValue, completedMatches));
  }

  const matchDemos = toFiniteNumber(valueAt(state, ["match", "stats", "demos"], 0), 0);
  const matchDeaths = toFiniteNumber(valueAt(state, ["match", "stats", "deaths"], 0), 0);
  const sessionDemos = toFiniteNumber(valueAt(state, ["session", "demos"], 0), 0);
  const sessionDeaths = toFiniteNumber(valueAt(state, ["session", "deaths"], 0), 0);
  setValue("matchKD", formatKillDeathRatio(matchDemos, matchDeaths));
  setValue("sessionKD", formatKillDeathRatio(sessionDemos, sessionDeaths));
  setValue("avgKD", formatKillDeathRatio(sessionDemos, sessionDeaths));
}

async function refreshLayout() {
  try {
    const response = await fetch(`/layout.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    const layout = await response.json();
    if (isRecord(layout)) {
      overlayLayout = layout;
      applyStatsSafezone();
    }
  } catch (error) {
    applyStatsSafezone();
  }
}

async function refresh() {
  try {
    const response = await fetch(`/state.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`state request failed: ${response.status}`);
    }
    const state = await response.json();
    const serialized = JSON.stringify(state);
    if (serialized !== previousState) {
      previousState = serialized;
      render(state);
    }
  } catch (error) {
    setFeedStatus("Feed unavailable");
  }
}

applyStatsSafezone();
refreshLayout();
refresh();
setInterval(refresh, 250);
window.addEventListener("resize", applyStatsSafezone);
