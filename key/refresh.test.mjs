import test from 'node:test';
import assert from 'node:assert/strict';
import {
  extractBalancedLiteral,
  extractPartnerContentIds,
  extractRemoteSnapshot,
  extractSupabaseAnonKey,
  normalizePartners,
  parseAppData,
} from './refresh.mjs';

test('extractBalancedLiteral handles nested brackets inside strings and comments', () => {
  const src = `const partners = [{name: "x ] }", perks: ["a"]}, /* ] */ {name: 'y'}]; const z = 1;`;
  const literal = extractBalancedLiteral(src, 'partners');
  assert.equal(literal, `[{name: "x ] }", perks: ["a"]}, /* ] */ {name: 'y'}]`);
});

test('parseAppData parses literal catalog and special offers', () => {
  const src = `const partners = [{name: "A", perksRu: ["P"]}];\nconst specialOffers = {ru:["R"], en:["E"]};`;
  const parsed = parseAppData(src);
  assert.equal(parsed.partners[0].name, 'A');
  assert.deepEqual(parsed.specialOffers.ru, ['R']);
});

test('parseAppData rejects executable constructs in extracted data', () => {
  const src = `const partners = [(() => ({name:"A"}))()]; const specialOffers = {ru:[],en:[]};`;
  assert.throws(() => parseAppData(src), /Executable construct rejected/u);
});

test('extractPartnerContentIds reads string array near contract marker', () => {
  const src = `const PARTNER_CONTENT_IDS = Object.freeze(["four-seasons", "marriott"]);`;
  assert.deepEqual(extractPartnerContentIds(src), ['four-seasons', 'marriott']);
});

test('extractSupabaseAnonKey supports named config and publishable key', () => {
  assert.equal(extractSupabaseAnonKey(`const SUPABASE_ANON_KEY = "abc.def.ghi";`), 'abc.def.ghi');
  assert.equal(extractSupabaseAnonKey(`const x = "sb_publishable_123-abc";`), 'sb_publishable_123-abc');
});

test('extractRemoteSnapshot supports known envelope shapes', () => {
  const snapshot = {version: 3, values: {}};
  assert.equal(extractRemoteSnapshot({data: {snapshot}}), snapshot);
  assert.equal(extractRemoteSnapshot({snapshot}), snapshot);
  assert.equal(extractRemoteSnapshot(snapshot), snapshot);
  assert.equal(extractRemoteSnapshot({ok:false, snapshot}), null);
});

test('normalizePartners applies Russian remote overrides and keeps provenance', () => {
  const base = [{
    name: 'Four Seasons Preferred Partner',
    logo: 'assets/x.webp',
    keyBrands: ['Four Seasons'],
    perksRu: ['Base perk 1', 'Base perk 2'],
    sourceLabel: 'Programme',
    sourceUrl: 'https://example.com/source',
    sourceAsOf: '2026-09-01',
    sourceConditions: 'Conditions',
  }];
  const snapshot = {values: {
    'partners.cards.fs.name': {ru: 'Four Seasons PP'},
    'partners.cards.fs.perk.1': {ru: 'Remote perk'},
    'partners.cards.fs.summary': {ru: 'Remote summary'},
  }};
  const [card] = normalizePartners(base, ['fs'], snapshot);
  assert.equal(card.id, 'fs');
  assert.equal(card.name, 'Four Seasons PP');
  assert.deepEqual(card.perks, ['Remote perk', 'Base perk 2']);
  assert.equal(card.summary, 'Remote summary');
  assert.equal(card.source.url, 'https://example.com/source');
  assert.equal(card.remote_overrides_applied, true);
});
