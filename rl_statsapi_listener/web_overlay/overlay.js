const $ = (id) => document.getElementById(id);

const fields = {
  blueScore: $("blueScore"),
  orangeScore: $("orangeScore"),
  clock: $("clock"),
  eventName: $("eventName"),
  eventBanner: $("eventBanner"),
  sessionWins: $("sessionWins"),
  sessionLosses: $("sessionLosses"),
  sessionStreak: $("sessionStreak"),
  sessionLowFives: $("sessionLowFives"),
  sessionHighFives: $("sessionHighFives"),
  sessionDemos: $("sessionDemos"),
  freeplayLast: $("freeplayLast"),
  freeplayBest: $("freeplayBest"),
  freeplayAllTime: $("freeplayAllTime"),
  clubName: $("clubName"),
  clubRecord: $("clubRecord"),
  recentMmr: $("recentMmr"),
  dejavuList: $("dejavuList"),
};

let previousState = "";

function valueAt(source, path, fallback = "") {
  let current = source;
  for (const key of path) {
    if (current === null || current === undefined || !(key in current)) {
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

function renderDejavu(players) {
  fields.dejavuList.replaceChildren();

  if (!Array.isArray(players) || players.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No recent history";
    fields.dejavuList.append(empty);
    return;
  }

  for (const player of players.slice(0, 6)) {
    const item = document.createElement("div");
    item.className = "dejavu-item";
    item.textContent = player.display || player.name || "";
    fields.dejavuList.append(item);
  }
}

function render(state) {
  setText(fields.blueScore, valueAt(state, ["scores", "blue"], 0));
  setText(fields.orangeScore, valueAt(state, ["scores", "orange"], 0));
  setText(fields.clock, state.clock || "0:00");
  setText(fields.eventName, valueAt(state, ["event", "name"], "Waiting"));

  const banner = valueAt(state, ["event", "banner"], "");
  setText(fields.eventBanner, banner);
  fields.eventBanner.hidden = !banner;

  setText(fields.sessionWins, valueAt(state, ["session", "wins"], 0));
  setText(fields.sessionLosses, valueAt(state, ["session", "losses"], 0));
  setText(fields.sessionStreak, valueAt(state, ["session", "streak"], 0));
  setText(fields.sessionLowFives, valueAt(state, ["session", "low_fives"], 0));
  setText(fields.sessionHighFives, valueAt(state, ["session", "high_fives"], 0));
  setText(fields.sessionDemos, valueAt(state, ["session", "demos"], 0));

  setText(fields.freeplayLast, valueAt(state, ["freeplay", "last_shot"], "-- kph"));
  setText(fields.freeplayBest, valueAt(state, ["freeplay", "session_best"], "-- kph"));
  setText(fields.freeplayAllTime, valueAt(state, ["freeplay", "all_time_best"], "-- kph"));

  setText(fields.clubName, valueAt(state, ["club", "name"], ""));
  setText(fields.clubRecord, valueAt(state, ["club", "record"], ""));
  setText(fields.recentMmr, valueAt(state, ["mmr", "recent"], "MMR pending"));
  renderDejavu(state.dejavu);
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
    setText(fields.eventName, "State feed error");
    setText(fields.eventBanner, "Overlay data feed unavailable");
    fields.eventBanner.hidden = false;
  }
}

refresh();
setInterval(refresh, 250);
