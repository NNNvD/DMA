const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const panelPath = path.join(
  __dirname,
  "../../backend/api/static/dm_panel.html",
);
const panel = fs.readFileSync(panelPath, "utf8");
const archivedIds = [
  "current-scene",
  "session-update-review",
  "import-review",
  "quick-rules",
  "quick-prep",
  "session-soundboard",
  "voice-reader",
  "reference-pdfs",
  "continuity-search",
  "session-context",
  "dma-chat-workbench",
];

test("archived modules stay out of active panels and tool launchers", () => {
  const archiveBlock = panel.match(
    /const ARCHIVED_MODULE_IDS = new Set\(\[([\s\S]*?)\]\);/,
  );
  assert.ok(archiveBlock, "panel must declare its explicit archive manifest");
  const declaredIds = [...archiveBlock[1].matchAll(/"([a-z-]+)"/g)].map(
    (match) => match[1],
  );
  assert.deepEqual(declaredIds, archivedIds);

  const toolBlock = panel.match(/const toolDefinitions = \[([\s\S]*?)\n    \];/);
  assert.ok(toolBlock, "panel must declare active tool launchers");
  const orderBlock = panel.match(
    /const defaultTopModuleIds = \[([\s\S]*?)\n    \];/,
  );
  assert.ok(orderBlock, "panel must declare active top-level modules");
  for (const id of archivedIds) {
    assert.doesNotMatch(toolBlock[1], new RegExp(`id: "${id}"`));
    assert.doesNotMatch(orderBlock[1], new RegExp(`"${id}"`));
  }
});

test("archived modules are parked before active layout initialization", () => {
  assert.ok(/id="archived-module-stash" hidden/.test(panel));
  assert.ok(/function archiveModulesFromActiveLayout\(\)/.test(panel));
  assert.ok(/stash\.appendChild\(panel\)/.test(panel));
  assert.ok(/archiveModulesFromActiveLayout\(\);\s*initializeModuleLayout\(\);/.test(panel));
});
