(function exposeCombatConditions(root) {
  function remainingDurationTurns(condition) {
    const value = condition?.durationTurns;
    if (typeof value === "number") {
      return Number.isSafeInteger(value) && value > 0 ? value : null;
    }
    if (typeof value === "string" && /^\d+$/.test(value.trim())) {
      const parsed = Number.parseInt(value, 10);
      return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
    }
    return null;
  }

  function finishCombatantTurn(conditions) {
    if (!Array.isArray(conditions)) return [];
    return conditions.flatMap((condition) => {
      const remaining = remainingDurationTurns(condition);
      if (remaining === null) return [condition];
      if (remaining === 1) return [];
      return [{ ...condition, durationTurns: remaining - 1 }];
    });
  }

  function createSerialWriteQueue() {
    let tail = Promise.resolve();
    return function enqueue(write) {
      const result = tail.then(write);
      tail = result.then(() => undefined, () => undefined);
      return result;
    };
  }

  const api = {
    remainingDurationTurns,
    finishCombatantTurn,
    createSerialWriteQueue,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.DmaCombatConditions = api;
  }
})(globalThis);
