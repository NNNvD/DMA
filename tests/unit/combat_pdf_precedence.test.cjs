const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const html = fs.readFileSync(path.join(__dirname, '../../backend/api/static/dm_panel.html'), 'utf8');

function sourceBetween(startName, nextName) {
  let start = html.indexOf(`    function ${startName}(`);
  if (start < 0) start = html.indexOf(`    async function ${startName}(`);
  const end = html.indexOf(`    function ${nextName}(`, start);
  assert.ok(start >= 0 && end > start, `${startName} source was not found`);
  return html.slice(start, end);
}

function lastSourceBetween(startName, nextName) {
  const start = html.lastIndexOf(`    function ${startName}(`);
  const end = html.indexOf(`    function ${nextName}(`, start);
  assert.ok(start >= 0 && end > start, `${startName} source was not found`);
  return html.slice(start, end);
}

const context = {
  roomLiteralParts: (room) => ({ gm: room.literal_text?.encounter_text || '' }),
  combatBlocksFromEncounterText: (text) => text.split(/\n\n(?=[A-Z’' ]+ CREATURE -?\d+)/),
  normalizedCombatText: (text) => text.trim(),
  parseCombatHeading: (heading) => ({
    name: heading.match(/^(.+?)\s+CREATURE/i)?.[1] || '',
    level: heading.match(/CREATURE\s+(-?\d+)/i)?.[1] || '',
  }),
  normalizeCreatureLookupName: (name) => String(name).toLowerCase().replace(/[’‘]/g, "'").replace(/s$/, ''),
  initiativeBonus: (combatant) => Number(combatant.initiative?.match(/[+-]\d+/)?.[0] || 0),
  firstNumber: (value) => Number(value?.match(/-?\d+/)?.[0]) || null,
  withCombatHp: (combatant) => ({ ...combatant, maxHp: Number(combatant.hp) || null }),
  campaignBestiaryDetailText: () => '',
  combatantFromAonCreature: (creature) => ({
    ...creature,
    initiative: `Perception ${creature.perception}`,
    initiativeBonus: Number(creature.perception),
    abilities: creature.actions || [],
    detail: creature.content || '',
  }),
  Math,
};
vm.createContext(context);
vm.runInContext([
  lastSourceBetween('normalizedCombatText', 'titleCaseName'),
  lastSourceBetween('titleCaseName', 'combatStatValue'),
  lastSourceBetween('withCombatHp', 'parseCombatHeading'),
  lastSourceBetween('parseCombatHeading', 'combatantFromBlock'),
  lastSourceBetween('combatBlocksFromEncounterText', 'combatantsFromRoom'),
  sourceBetween('campaignPdfCombatOverrides', 'combatantFromCampaignBestiaryEntry'),
  sourceBetween('combatantFromCampaignBestiaryEntry', 'combatantFromCampaignAonReference'),
  sourceBetween('combatantFromCampaignAonReference', 'mergeAonDetailsIntoCombatant'),
  sourceBetween('mergeAonDetailsIntoCombatant', 'aonCreatureUrlForMatch'),
  sourceBetween('refreshMonsterCombatantsFromAon', 'refreshCombatantImagesFromBestiary'),
  html.slice(
    html.lastIndexOf('    function combatantFromAonCreature('),
    html.indexOf('    async function addSelectedAonCreature(', html.lastIndexOf('    function combatantFromAonCreature(')),
  ),
].join('\n'), context);

test('active AoN converter keeps detailed fields for combat cards', () => {
  const result = context.combatantFromAonCreature({
    creature_id: 461, name: 'Evangelist', level: 6, perception: '+12',
    traits: ['velstrac'], senses: 'darkvision', languages: 'Common',
    skills: ['Intimidation +15'], ability_mods: { str: '+4' },
    immunities: 'cold', weaknesses: 'good 5', resistances: 'physical 5',
    attacks: ['Melee chain +17'], actions: ['Animate Chains'], spells: ['Divine Spells'],
  });
  assert.equal(result.abilities[0], 'Animate Chains');
  assert.equal(result.senses, 'darkvision');
  assert.equal(result.languages, 'Common');
  assert.equal(result.skills[0], 'Intimidation +15');
  assert.equal(result.abilityMods.str, '+4');
  assert.equal(result.resistances, 'physical 5');
  assert.equal(result.spells[0], 'Divine Spells');
});

test('campaign PDF stats and attacks survive AoN enrichment', () => {
  const room = {
    room_id: 'TEST-1',
    encounter_refs: [{ id: 'captain' }, { id: 'companion' }],
    literal_text: { encounter_text: 'SAMPLE CAPTAIN CREATURE 6\nHP 99\n\nSAMPLE COMPANION CREATURE 4\nPerception +9\nAC 20; Fort +8, Ref +11, Will +7\nHP 50\nSpeed 30 feet' },
  };
  const entry = {
    id: 'companion', name: 'Sample Companion', level: 4, entry_type: 'aon_reference',
    combat: { attacks: ['Melee strike +12, Damage 2d6+5 bludgeoning'] },
  };
  const base = context.combatantFromCampaignAonReference(entry, { room });
  assert.equal(context.combatBlocksFromEncounterText(room.literal_text.encounter_text).length, 2);
  assert.equal(base.campaignOverrides.hp, '50', JSON.stringify(base.campaignOverrides));
  const result = context.mergeAonDetailsIntoCombatant(base, {
    name: 'Companion', level: 1, hp: '22', ac: '15', fort: '+6', ref: '+7', will: '+4',
    speed: '30 feet', perception: '+7', attacks: ['Melee strike +7'], actions: [],
  });
  assert.equal(result.level, 4);
  assert.equal(result.hp, '50');
  assert.equal(result.ac, '20');
  assert.equal(result.fort, '+8');
  assert.equal(result.attacks[0], entry.combat.attacks[0]);
});

test('partial PDF block retains initiative while AoN supplies missing stats', () => {
  const room = {
    room_id: 'TEST-2', encounter_refs: [{ id: 'sentinel' }],
    literal_text: { encounter_text: 'SAMPLE SENTINEL CREATURE 6\nInitiative Perception +13' },
  };
  const entry = { id: 'sentinel', name: 'Sample Sentinel', level: 6, entry_type: 'creature' };
  const base = context.combatantFromCampaignBestiaryEntry(entry, { room });
  assert.equal(base.campaignOverrides.initiative, 'Perception +13', JSON.stringify(base.campaignOverrides));
  const result = context.mergeAonDetailsIntoCombatant(base, {
    name: 'Reference Creature', level: 6, hp: '90', ac: '24', perception: '+12',
    attacks: ['Melee lash +17'], actions: ['Sample Action'],
  });
  assert.equal(result.name, 'Sample Sentinel');
  assert.equal(result.initiative, 'Perception +13');
  assert.equal(result.hp, '90');
  assert.equal(result.ac, '24');
  assert.equal(result.abilities[0], 'Sample Action');
});

test('PDF minus signs remain negative ability modifiers', () => {
  const room = {
    encounter_refs: [{ id: 'sample' }],
    literal_text: { encounter_text: 'SAMPLE GUARD CREATURE 6\nStr +3, Dex +2, Con +0, Int –1, Wis +4, Cha +2' },
  };
  const overrides = context.campaignPdfCombatOverrides({ id: 'sample', name: 'Sample Guard', level: 6 }, room);
  assert.equal(overrides.abilityMods.int, '-1');
});

test('saved custom combatant receives PDF stats without an AoN match', async () => {
  const entry = { id: 'sample', name: 'Sample Unique Creature', level: 7, entry_type: 'creature' };
  const room = {
    room_id: 'TEST-3', encounter_refs: [{ id: 'sample' }],
    literal_text: { encounter_text: 'SAMPLE UNIQUE CREATURE CREATURE 7\nPerception +12\nAC 25; Fort +10, Ref +13, Will +11\nHP 85' },
  };
  context.bestiaryEntryById = (id) => id === 'sample' ? entry : null;
  context.activeRoomKey = { rooms: [room] };
  context.currentCombat = { combatants: [{ id: 'old-sample', bestiaryId: 'sample', roomId: 'TEST-3', name: 'Sample Unique Creature', hpTrack: [42] }] };
  context.findAonCreatureForCombatant = () => null;
  context.labelDuplicateCombatants = (items) => items;
  context.syncActiveCombatExpansion = () => {};
  context.commitCombatState = () => {};

  await context.refreshMonsterCombatantsFromAon();

  const updated = context.currentCombat.combatants[0];
  assert.equal(updated.hp, '85');
  assert.equal(updated.ac, '25');
  assert.equal(updated.maxHp, 85);
  assert.equal(updated.hpTrack[0], 42);
});

const privateRoot = path.join(__dirname, '../../local-private-overlay/project-root/assets/imports/misc/private-local');
const level4Rooms = path.join(privateRoot, 'room-keys/abomination-vaults/level-4.json');
const level4Bestiary = path.join(privateRoot, 'bestiary/abomination-vaults/level-4.json');
test('all local level-4 encounter references match PDF blocks and have usable stats', {
  skip: !fs.existsSync(level4Rooms) || !fs.existsSync(level4Bestiary),
}, () => {
  const rooms = JSON.parse(fs.readFileSync(level4Rooms, 'utf8')).rooms;
  const entries = new Map(JSON.parse(fs.readFileSync(level4Bestiary, 'utf8')).entries.map((entry) => [entry.id, entry]));
  const cacheRoot = path.join(__dirname, '../../assets/imports/misc/aon-creatures/raw');
  let encounters = 0;
  for (const room of rooms) {
    const refs = room.encounter_refs || [];
    if (!refs.length) continue;
    const blocks = context.combatBlocksFromEncounterText(context.roomLiteralParts(room).gm);
    assert.equal(blocks.length, refs.length, `${room.room_id} block count`);
    for (const ref of refs) {
      const entry = entries.get(ref.id);
      assert.ok(entry, `${room.room_id} ${ref.id} is missing`);
      const combatant = entry.entry_type === 'aon_reference'
        ? context.combatantFromCampaignAonReference(entry, { room, count: ref.count })
        : context.combatantFromCampaignBestiaryEntry(entry, { room, count: ref.count });
      assert.equal(combatant.level, entry.level, `${room.room_id} ${entry.name} level`);
      assert.ok(combatant.initiative, `${room.room_id} ${entry.name} initiative`);
      let complete = combatant;
      if (entry.aon_creature_id && fs.existsSync(cacheRoot)) {
        const cache = fs.readdirSync(cacheRoot).find((name) => name.startsWith(`${entry.aon_creature_id}-`));
        if (cache) {
          complete = context.mergeAonDetailsIntoCombatant(combatant, JSON.parse(fs.readFileSync(path.join(cacheRoot, cache), 'utf8')));
        }
      }
      assert.ok(complete.hp && complete.ac, `${room.room_id} ${entry.name} full stats`);
      assert.ok(complete.attacks.length, `${room.room_id} ${entry.name} attacks`);
      encounters += 1;
    }
  }
  assert.ok(encounters > 0);
});
