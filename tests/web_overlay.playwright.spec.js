const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");

const { expect, test } = require("@playwright/test");

const REPO_ROOT = path.resolve(__dirname, "..");
const WEB_ROOT = path.join(REPO_ROOT, "rl_statsapi_listener", "web_overlay");
const MEDIA_ROOT = path.join(REPO_ROOT, "media");

const LAYOUT = {
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
        size: { w: 1567, h: 51 },
        position: { x: 892, y: 1289 },
      },
    },
  },
  scoreboard_layouts: {},
  warnings: [],
};

const MATCH_STATE = {
  context: { mode: "match", active: true, freeplay: false },
  event: { name: "UpdateState", banner: "" },
  match: {
    guid: "demo",
    playlist_id: 11,
    own_team: 0,
    winner_team: null,
    stats: { goals: 2, assists: 1, saves: 3, shots: 5, demos: 1, high_fives: 0, low_fives: 1 },
  },
  session: {
    wins: 4,
    losses: 2,
    streak: "W2",
    goals: 12,
    assists: 7,
    saves: 18,
    shots: 29,
    demos: 7,
    high_fives: 1,
    low_fives: 3,
  },
};

const MENU_STATE = {
  context: { mode: "menu", active: false, freeplay: false },
  event: { name: "MatchDestroyed", banner: "" },
  match: { guid: null, stats: {} },
  session: {
    wins: 6,
    losses: 4,
    streak: "L1",
    goals: 0,
    assists: 0,
    saves: 0,
    shots: 0,
    demos: 2,
    high_fives: 0,
    low_fives: 1,
  },
};

function contentType(filePath) {
  if (filePath.endsWith(".html")) return "text/html; charset=utf-8";
  if (filePath.endsWith(".css")) return "text/css; charset=utf-8";
  if (filePath.endsWith(".js")) return "application/javascript; charset=utf-8";
  if (filePath.endsWith(".webp")) return "image/webp";
  return "application/octet-stream";
}

async function sendJson(response, payload) {
  const body = Buffer.from(JSON.stringify(payload));
  response.writeHead(200, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Content-Length": body.length,
  });
  response.end(body);
}

async function sendFile(response, root, relativePath) {
  const filePath = path.resolve(root, relativePath);
  const rootPath = path.resolve(root);
  if (!filePath.startsWith(`${rootPath}${path.sep}`)) {
    response.writeHead(404);
    response.end();
    return;
  }

  try {
    const body = await fs.readFile(filePath);
    response.writeHead(200, {
      "Content-Type": contentType(filePath),
      "Cache-Control": "no-store",
      "Content-Length": body.length,
    });
    response.end(body);
  } catch (error) {
    response.writeHead(404);
    response.end();
  }
}

async function startOverlayServer(state) {
  const server = http.createServer(async (request, response) => {
    const url = new URL(request.url, "http://127.0.0.1");
    if (url.pathname === "/" || url.pathname === "/index.html") {
      await sendFile(response, WEB_ROOT, "index.html");
      return;
    }
    if (url.pathname === "/styles.css" || url.pathname === "/overlay.js") {
      await sendFile(response, WEB_ROOT, url.pathname.slice(1));
      return;
    }
    if (url.pathname === "/layout.json") {
      await sendJson(response, LAYOUT);
      return;
    }
    if (url.pathname === "/state.json") {
      await sendJson(response, state);
      return;
    }
    if (url.pathname.startsWith("/media/")) {
      await sendFile(response, MEDIA_ROOT, url.pathname.slice("/media/".length));
      return;
    }

    response.writeHead(404);
    response.end();
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  return {
    url: `http://127.0.0.1:${port}/`,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

async function expectRoundedBox(locator, expected) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  expect(Math.round(box.x)).toBe(expected.x);
  expect(Math.round(box.y)).toBe(expected.y);
  expect(Math.round(box.width)).toBe(expected.w);
  expect(Math.round(box.height)).toBe(expected.h);
}

test("match state uses match.stats and renders the in-match stats panel", async ({ page }, testInfo) => {
  const server = await startOverlayServer(MATCH_STATE);
  try {
    await page.goto(server.url);

    const safezone = page.locator("#statsSafezone");
    await expect(safezone).toHaveAttribute("data-layout", "match");
    await expect(safezone).toHaveAttribute("data-safezone-rect", "0,802,422,447");
    await expect(page.locator(".match-panel")).toBeVisible();
    await expect(page.locator(".menu-strip")).toBeHidden();
    await expect(page.locator('[data-value="matchGoals"]').first()).toHaveText("2");
    await expect(page.locator('[data-value="sessionGoals"]').first()).toHaveText("12");
    await expect(page.locator('[data-value="avgGoals"]').first()).toHaveText("2");

    await expectRoundedBox(safezone, { x: 0, y: 802, w: 422, h: 447 });

    const allIconsLoaded = await page.locator(".match-panel img").evaluateAll((images) =>
      images.every((image) => image.complete && image.naturalWidth > 0 && image.naturalHeight > 0),
    );
    expect(allIconsLoaded).toBe(true);

    await safezone.screenshot({ path: testInfo.outputPath("match-stats-panel.png"), omitBackground: true });
  } finally {
    await server.close();
  }
});

test("menu state uses menu.stats and renders the compact strip", async ({ page }, testInfo) => {
  const server = await startOverlayServer(MENU_STATE);
  try {
    await page.goto(server.url);

    const safezone = page.locator("#statsSafezone");
    await expect(safezone).toHaveAttribute("data-layout", "menu");
    await expect(safezone).toHaveAttribute("data-safezone-rect", "892,1289,1567,51");
    await expect(page.locator(".menu-strip")).toBeVisible();
    await expect(page.locator(".match-panel")).toBeHidden();
    await expect(page.locator('.menu-strip [data-value="sessionWinRate"]').first()).toHaveText("60.00");
    await expect(page.locator('.menu-strip [data-value="sessionStreak"]').first()).toHaveText("-1");

    await expectRoundedBox(safezone, { x: 892, y: 1289, w: 1567, h: 51 });

    const allIconsLoaded = await page.locator(".menu-strip img").evaluateAll((images) =>
      images.every((image) => image.complete && image.naturalWidth > 0 && image.naturalHeight > 0),
    );
    expect(allIconsLoaded).toBe(true);

    await safezone.screenshot({ path: testInfo.outputPath("menu-stats-strip.png"), omitBackground: true });
  } finally {
    await server.close();
  }
});
