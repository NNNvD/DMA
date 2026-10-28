const test = require("node:test");
const assert = require("node:assert/strict");

const {
  finishCombatantTurn,
  remainingDurationTurns,
  createSerialWriteQueue,
} = require("../../backend/api/static/combat_conditions.js");

test("condition magnitude does not become an automatic duration", () => {
  const condition = { name: "frightened", value: "2", timing: "turn" };
  assert.equal(remainingDurationTurns(condition), null);
  assert.deepEqual(finishCombatantTurn([condition]), [condition]);
});

test("an explicit duration decreases at the end of the affected turn", () => {
  const conditions = [
    { name: "slowed", value: "1", durationTurns: 2 },
    { name: "frightened", value: "2" },
  ];
  assert.deepEqual(finishCombatantTurn(conditions), [
    { name: "slowed", value: "1", durationTurns: 1 },
    { name: "frightened", value: "2" },
  ]);
  assert.deepEqual(conditions[0], {
    name: "slowed",
    value: "1",
    durationTurns: 2,
  });
});

test("a one turn duration expires after that combatant acts", () => {
  assert.deepEqual(
    finishCombatantTurn([
      { name: "frightened", value: "1", durationTurns: 1 },
      { name: "persistent damage", value: "1d6 fire", timing: "round" },
    ]),
    [{ name: "persistent damage", value: "1d6 fire", timing: "round" }],
  );
});

test("invalid or absent durations remain manual conditions", () => {
  for (const durationTurns of [0, -1, 1.5, "", "later"]) {
    assert.equal(remainingDurationTurns({ durationTurns }), null);
  }
});

test("session writes run in order even when a request rejects", async () => {
  const enqueue = createSerialWriteQueue();
  const order = [];
  const first = enqueue(async () => {
    order.push("first-start");
    await new Promise((resolve) => setTimeout(resolve, 10));
    order.push("first-fail");
    throw new Error("network failure");
  });
  const second = enqueue(async () => {
    order.push("second");
    return "saved";
  });

  await assert.rejects(first, /network failure/);
  assert.equal(await second, "saved");
  assert.deepEqual(order, ["first-start", "first-fail", "second"]);
});

test("a reset waits for an in-flight save and later queued saves stay ordered", async () => {
  const enqueue = createSerialWriteQueue();
  const order = [];
  let releaseSave;
  const pendingSave = enqueue(async () => {
    order.push("save-start");
    await new Promise((resolve) => { releaseSave = resolve; });
    order.push("save-end");
  });
  const pendingReset = enqueue(async () => {
    order.push("reset");
  });
  const laterSave = enqueue(async () => {
    order.push("later-save");
  });

  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(order, ["save-start"]);
  releaseSave();
  await Promise.all([pendingSave, pendingReset, laterSave]);
  assert.deepEqual(order, ["save-start", "save-end", "reset", "later-save"]);
});

test("a conflict rejects the write without advancing revision or dropping local data", async () => {
  const enqueue = createSerialWriteQueue();
  let revision = 8;
  const localState = { scene_title: "Keep this edit" };
  const conflict = Object.assign(new Error("stale revision"), { status: 409 });

  await assert.rejects(enqueue(async () => {
    assert.equal(revision, 8);
    assert.equal(localState.scene_title, "Keep this edit");
    throw conflict;
  }), (error) => error.status === 409);
  assert.equal(revision, 8);
  assert.equal(localState.scene_title, "Keep this edit");
});
