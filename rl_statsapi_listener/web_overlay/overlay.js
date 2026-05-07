const $ = (id) => document.getElementById(id);

const DEFAULT_LAYOUT = {
  reference_resolution: { w: 2560, h: 1140 },
  safezones: {
    match: {
      stats: {
        size: { w: 422, h: 447 },
        position: { x: 0, y: 802 },
      },
    },
  },
  scoreboard_layouts: {},
};
const DEFAULT_STATS_RECT = { x: 0, y: 802, w: 422, h: 447 };

const fields = {
  statsSafezone: $("statsSafezone"),
  sessionWins: $("sessionWins"),
  sessionLosses: $("sessionLosses"),
  sessionStreak: $("sessionStreak"),
  sessionLowFives: $("sessionLowFives"),
  sessionHighFives: $("sessionHighFives"),
  sessionDemos: $("sessionDemos"),
  careerLowFives: $("careerLowFives"),
  careerHighFives: $("careerHighFives"),
  careerDemos: $("careerDemos"),
  freeplayLast: $("freeplayLast"),
  freeplayBest: $("freeplayBest"),
  freeplayAllTime: $("freeplayAllTime"),
  clubName: $("clubName"),
  clubRecord: $("clubRecord"),
  recentMmr: $("recentMmr"),
  dejavuList: $("dejavuList"),
  feedStatus: $("feedStatus"),
};

let previousState = "";
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
  if (element.textContent !== text) {
    element.textContent = text;
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

function statsSafezoneSpec() {
  return valueAt(
    overlayLayout,
    ["safezones", "match", "stats"],
    valueAt(DEFAULT_LAYOUT, ["safezones", "match", "stats"]),
  );
}

function statsSafezoneRect() {
  const spec = statsSafezoneSpec();
  const rect = {
    x: toFiniteNumber(valueAt(spec, ["position", "x"], DEFAULT_STATS_RECT.x), DEFAULT_STATS_RECT.x),
    y: toFiniteNumber(valueAt(spec, ["position", "y"], DEFAULT_STATS_RECT.y), DEFAULT_STATS_RECT.y),
    w: toFiniteNumber(valueAt(spec, ["size", "w"], DEFAULT_STATS_RECT.w), DEFAULT_STATS_RECT.w),
    h: toFiniteNumber(valueAt(spec, ["size", "h"], DEFAULT_STATS_RECT.h), DEFAULT_STATS_RECT.h),
  };

  if (rect.w <= 0 || rect.h <= 0) {
    return { ...DEFAULT_STATS_RECT };
  }
  return rect;
}

function referenceResolution() {
  const reference = valueAt(overlayLayout, ["reference_resolution"], DEFAULT_LAYOUT.reference_resolution);
  return {
    w: Math.max(1, toFiniteNumber(reference.w, DEFAULT_LAYOUT.reference_resolution.w)),
    h: Math.max(1, toFiniteNumber(reference.h, DEFAULT_LAYOUT.reference_resolution.h)),
  };
}

function applyStatsSafezone() {
  const rect = statsSafezoneRect();
  const reference = referenceResolution();
  const scaleX = window.innerWidth / reference.w;
  const scaleY = window.innerHeight / reference.h;

  fields.statsSafezone.style.left = `${rect.x * scaleX}px`;
  fields.statsSafezone.style.top = `${rect.y * scaleY}px`;
  fields.statsSafezone.style.width = `${rect.w * scaleX}px`;
  fields.statsSafezone.style.height = `${rect.h * scaleY}px`;
}

function renderDejavu(players) {
  fields.dejavuList.replaceChildren();

  if (!Array.isArray(players) || players.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No recent history";
    fields.dejavuList.append(empty);
    return;
  }

  for (const player of players.slice(0, 5)) {
    const item = document.createElement("div");
    item.className = "dejavu-item";
    item.textContent = player.display || player.name || "";
    fields.dejavuList.append(item);
  }
}

function render(state) {
  setFeedStatus("");

  setText(fields.sessionWins, valueAt(state, ["session", "wins"], 0));
  setText(fields.sessionLosses, valueAt(state, ["session", "losses"], 0));
  setText(fields.sessionStreak, valueAt(state, ["session", "streak"], 0));
  setText(fields.sessionLowFives, valueAt(state, ["session", "low_fives"], 0));
  setText(fields.sessionHighFives, valueAt(state, ["session", "high_fives"], 0));
  setText(fields.sessionDemos, valueAt(state, ["session", "demos"], 0));

  setText(fields.careerLowFives, valueAt(state, ["career", "low_fives"], 0));
  setText(fields.careerHighFives, valueAt(state, ["career", "high_fives"], 0));
  setText(fields.careerDemos, valueAt(state, ["career", "demos"], 0));

  setText(fields.freeplayLast, valueAt(state, ["freeplay", "last_shot"], "-- kph"));
  setText(fields.freeplayBest, valueAt(state, ["freeplay", "session_best"], "-- kph"));
  setText(fields.freeplayAllTime, valueAt(state, ["freeplay", "all_time_best"], "-- kph"));

  setText(fields.clubName, valueAt(state, ["club", "name"], ""));
  setText(fields.clubRecord, valueAt(state, ["club", "record"], ""));
  setText(fields.recentMmr, valueAt(state, ["mmr", "recent"], "MMR pending"));
  renderDejavu(state.dejavu);
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
