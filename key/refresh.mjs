import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';

export const APP_BASE = 'https://traveltg-bot.netlify.app';
export const DATA_URL = `${APP_BASE}/lib/data.js`;
export const CONTRACT_URL = `${APP_BASE}/lib/content/contract.js`;
export const SUPABASE_CONFIG_URL = `${APP_BASE}/lib/supabase.js`;
export const MINIAPP_CONTENT_URL = 'https://qymhzqkenzsgszogkcdq.supabase.co/functions/v1/miniapp-content?locale=ru&environment=production';

const MIN_PARTNERS = 20;
const FETCH_TIMEOUT_MS = 20_000;
const MAX_TEXT_BYTES = 2_000_000;
const REMOTE_SUFFIXES = [
  'name', 'hotel_count', 'summary', 'brands', 'scope', 'favorites_label',
  ...Array.from({ length: 8 }, (_, i) => `perk.${i + 1}`),
  ...Array.from({ length: 4 }, (_, i) => `favorite.${i + 1}`),
  ...Array.from({ length: 4 }, (_, i) => `fresh.${i + 1}`),
];

const isObject = (value) => Boolean(value) && typeof value === 'object' && !Array.isArray(value);
const strings = (value) => Array.isArray(value) ? value.filter((item) => typeof item === 'string') : [];
const text = (value) => typeof value === 'string' ? value : '';

function stripStringsAndComments(source) {
  let out = '';
  let state = 'code';
  let quote = '';

  for (let i = 0; i < source.length; i += 1) {
    const ch = source[i];
    const next = source[i + 1];

    if (state === 'string') {
      if (ch === '\\') i += 1;
      else if (ch === quote) state = 'code';
      out += ch === '\n' ? '\n' : ' ';
      continue;
    }
    if (state === 'line-comment') {
      if (ch === '\n') {
        state = 'code';
        out += '\n';
      } else out += ' ';
      continue;
    }
    if (state === 'block-comment') {
      if (ch === '*' && next === '/') {
        state = 'code';
        out += '  ';
        i += 1;
      } else out += ch === '\n' ? '\n' : ' ';
      continue;
    }

    if (ch === '"' || ch === "'" || ch === '`') {
      state = 'string';
      quote = ch;
      out += ' ';
    } else if (ch === '/' && next === '/') {
      state = 'line-comment';
      out += '  ';
      i += 1;
    } else if (ch === '/' && next === '*') {
      state = 'block-comment';
      out += '  ';
      i += 1;
    } else out += ch;
  }
  return out;
}

export function extractBalancedLiteral(source, variableName) {
  const escaped = variableName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = new RegExp(`\\b(?:const|let|var)\\s+${escaped}\\s*=`, 'u').exec(source);
  if (!match) throw new Error(`Assignment not found: ${variableName}`);

  let start = match.index + match[0].length;
  while (/\s/u.test(source[start] || '')) start += 1;

  const opener = source[start];
  const closer = opener === '[' ? ']' : opener === '{' ? '}' : null;
  if (!closer) throw new Error(`Expected array/object literal for ${variableName}`);

  let depth = 0;
  let state = 'code';
  let quote = '';

  for (let i = start; i < source.length; i += 1) {
    const ch = source[i];
    const next = source[i + 1];

    if (state === 'string') {
      if (ch === '\\') i += 1;
      else if (ch === quote) state = 'code';
      continue;
    }
    if (state === 'line-comment') {
      if (ch === '\n') state = 'code';
      continue;
    }
    if (state === 'block-comment') {
      if (ch === '*' && next === '/') {
        state = 'code';
        i += 1;
      }
      continue;
    }

    if (ch === '"' || ch === "'" || ch === '`') {
      state = 'string';
      quote = ch;
    } else if (ch === '/' && next === '/') {
      state = 'line-comment';
      i += 1;
    } else if (ch === '/' && next === '*') {
      state = 'block-comment';
      i += 1;
    } else if (ch === opener) depth += 1;
    else if (ch === closer && --depth === 0) return source.slice(start, i + 1);
  }

  throw new Error(`Unterminated literal for ${variableName}`);
}

function evaluateDataLiteral(literal, label) {
  const forbidden = /=>|\bfunction\b|\bnew\b|\bclass\b|\bawait\b|\byield\b|\bimport\b|\brequire\b|\bprocess\b|\bglobalThis\b|\bconstructor\b|__proto__|\bthis\b/u;
  if (forbidden.test(stripStringsAndComments(literal))) {
    throw new Error(`Executable construct rejected in ${label}`);
  }
  const value = vm.runInNewContext(`(${literal})`, Object.create(null), { timeout: 250, displayErrors: true });
  return JSON.parse(JSON.stringify(value));
}

export function parseAppData(source) {
  const partners = evaluateDataLiteral(extractBalancedLiteral(source, 'partners'), 'partners');
  const specialOffers = evaluateDataLiteral(extractBalancedLiteral(source, 'specialOffers'), 'specialOffers');
  if (!Array.isArray(partners)) throw new Error('partners is not an array');
  if (!isObject(specialOffers)) throw new Error('specialOffers is not an object');
  return { partners, specialOffers };
}

export function extractPartnerContentIds(source) {
  const marker = source.indexOf('PARTNER_CONTENT_IDS');
  const open = marker < 0 ? -1 : source.indexOf('[', marker);
  if (open < 0) return [];
  try {
    const ids = evaluateDataLiteral(extractBalancedLiteral(`const ids = ${source.slice(open)}`, 'ids'), 'PARTNER_CONTENT_IDS');
    return Array.isArray(ids) && ids.every((value) => typeof value === 'string') ? ids : [];
  } catch {
    return [];
  }
}

export function extractSupabaseAnonKey(source) {
  const patterns = [
    /(?:SUPABASE_ANON_KEY|supabaseAnonKey|anonKey)\s*[:=]\s*['"]([^'"]+)['"]/u,
    /['"](sb_publishable_[A-Za-z0-9._-]+)['"]/u,
    /['"](eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)['"]/u,
  ];
  for (const pattern of patterns) {
    const match = pattern.exec(source);
    if (match) return match[1];
  }
  return '';
}

export function extractRemoteSnapshot(payload) {
  if (!isObject(payload) || payload.ok === false) return null;
  if (isObject(payload.data?.snapshot)) return payload.data.snapshot;
  if (isObject(payload.snapshot)) return payload.snapshot;
  return isObject(payload.values) ? payload : null;
}

function remoteRu(snapshot, fieldId, fallback = '') {
  const value = snapshot?.values?.[fieldId]?.ru;
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function absoluteAsset(path) {
  if (typeof path !== 'string' || !path) return '';
  try {
    return new URL(path, `${APP_BASE}/`).toString();
  } catch {
    return path;
  }
}

function remoteList(snapshot, field, stem, count, fallback = []) {
  return Array.from({ length: count }, (_, i) => remoteRu(snapshot, field(`${stem}.${i + 1}`), fallback[i] || '')).filter(Boolean);
}

export function normalizePartners(basePartners, contentIds = [], remoteSnapshot = null) {
  return basePartners.map((partner, index) => {
    if (!isObject(partner)) throw new Error(`Invalid partner at index ${index}`);
    if (!text(partner.name).trim()) throw new Error(`Partner ${index} has no name`);

    const id = text(partner.contentId) || contentIds[index] || `partner-${index + 1}`;
    const field = (suffix) => `partners.cards.${id}.${suffix}`;
    const baseBrands = strings(partner.keyBrands);
    const fallbackPerks = isObject(partner.perkCopyRu) && Array.isArray(partner.perkIds)
      ? partner.perkIds.map((perkId) => partner.perkCopyRu?.[perkId]).filter(Boolean)
      : strings(partner.perksRu).length ? strings(partner.perksRu) : strings(partner.perks);
    const fallbackSummary = partner.editorial || partner.portfolioDescriptionRu || partner.portfolioDescription || '';

    return {
      id,
      name: remoteRu(remoteSnapshot, field('name'), partner.name),
      logo: absoluteAsset(partner.logo),
      brands: baseBrands,
      brands_text: remoteRu(remoteSnapshot, field('brands'), baseBrands.join(' · ')),
      hotel_count: remoteRu(remoteSnapshot, field('hotel_count'), partner.hotelCount || ''),
      summary: remoteRu(remoteSnapshot, field('summary'), fallbackSummary),
      scope: remoteRu(remoteSnapshot, field('scope'), partner.perkScope || ''),
      perks: remoteList(remoteSnapshot, field, 'perk', 8, fallbackPerks),
      favorites_label: remoteRu(remoteSnapshot, field('favorites_label'), partner.favoritesLabel || 'Любимые адреса'),
      favorites: remoteList(remoteSnapshot, field, 'favorite', 4, partner.favorites),
      fresh: remoteList(remoteSnapshot, field, 'fresh', 4, partner.fresh),
      source: {
        label: text(partner.sourceLabel),
        url: text(partner.sourceUrl),
        as_of: text(partner.sourceAsOf),
        conditions: text(partner.sourceConditions),
      },
      remote_overrides_applied: Boolean(remoteSnapshot && REMOTE_SUFFIXES.some((suffix) => remoteRu(remoteSnapshot, field(suffix)))),
    };
  });
}

async function fetchText(url, headers = {}) {
  const response = await fetch(url, {
    headers: {
      Accept: '*/*',
      'User-Agent': 'key-privileges-refresh/1.0 (+https://github.com/Floppa2003/key-privileges)',
      ...headers,
    },
    cache: 'no-store',
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}`);

  const declaredLength = Number(response.headers.get('content-length'));
  if (Number.isFinite(declaredLength) && declaredLength > MAX_TEXT_BYTES) throw new Error(`${url} response too large`);

  const body = await response.text();
  if (Buffer.byteLength(body) > MAX_TEXT_BYTES) throw new Error(`${url} response too large`);
  return body;
}

async function fetchJson(url, headers = {}) {
  const body = await fetchText(url, { Accept: 'application/json', ...headers });
  try {
    return JSON.parse(body);
  } catch {
    throw new Error(`${url} returned invalid JSON`);
  }
}

async function tryRemoteSnapshot(warnings) {
  let anonKey = '';
  try {
    anonKey = extractSupabaseAnonKey(await fetchText(SUPABASE_CONFIG_URL));
    if (!anonKey) warnings.push('Supabase anon key was not found in public app config; trying endpoint without it.');
  } catch (error) {
    warnings.push(`Could not read public Supabase config: ${error.message}`);
  }

  try {
    const snapshot = extractRemoteSnapshot(await fetchJson(MINIAPP_CONTENT_URL, anonKey ? { apikey: anonKey } : {}));
    if (!snapshot) throw new Error('response did not contain a recognizable snapshot');
    return { snapshot, ok: true };
  } catch (error) {
    warnings.push(`Supabase content override unavailable: ${error.message}`);
    return { snapshot: null, ok: false };
  }
}

const stableHash = (value) => crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');

async function requestIdForEvent() {
  if ((process.env.GITHUB_EVENT_NAME || 'local') !== 'push') return null;
  try {
    const trigger = JSON.parse(await fs.readFile(new URL('./trigger.json', import.meta.url), 'utf8'));
    return text(trigger.request_id) || null;
  } catch {
    return null;
  }
}

export async function buildSnapshot() {
  const warnings = [];
  const fetchedAt = new Date().toISOString();
  const { partners: basePartners, specialOffers } = parseAppData(await fetchText(DATA_URL));
  if (basePartners.length < MIN_PARTNERS) {
    throw new Error(`Refusing to publish: recovered only ${basePartners.length} partners (<${MIN_PARTNERS})`);
  }

  let contentIds = [];
  try {
    contentIds = extractPartnerContentIds(await fetchText(CONTRACT_URL));
    if (contentIds.length !== basePartners.length) {
      warnings.push(`Partner content ID count ${contentIds.length} does not match partner count ${basePartners.length}; remote card overrides disabled.`);
    }
  } catch (error) {
    warnings.push(`Could not read partner content IDs: ${error.message}`);
  }

  const remote = await tryRemoteSnapshot(warnings);
  const remoteOk = remote.ok && contentIds.length === basePartners.length;
  const partners = normalizePartners(basePartners, contentIds, remoteOk ? remote.snapshot : null);
  const special = { ru: strings(specialOffers.ru), en: strings(specialOffers.en) };
  const contentCore = { partners, special_offers: special };
  const contentHash = stableHash(contentCore);
  const sourceMode = remoteOk ? 'netlify+supabase' : 'netlify';

  const catalog = {
    schema_version: 1,
    fetched_at: fetchedAt,
    source_mode: sourceMode,
    remote_ok: remoteOk,
    source_urls: {
      base_catalog: DATA_URL,
      content_contract: CONTRACT_URL,
      remote_content: MINIAPP_CONTENT_URL,
    },
    remote_snapshot: remoteOk ? {
      version: remote.snapshot?.version ?? null,
      published_at: remote.snapshot?.published_at ?? remote.snapshot?.publishedAt ?? null,
      schema_version: remote.snapshot?.schema_version ?? null,
    } : null,
    content_sha256: contentHash,
    ...contentCore,
  };

  return {
    catalog,
    status: {
      schema_version: 1,
      ok: true,
      fetched_at: fetchedAt,
      request_id: await requestIdForEvent(),
      triggered_by: process.env.GITHUB_EVENT_NAME || 'local',
      partner_count: partners.length,
      special_offer_count: special.ru.length,
      remote_ok: remoteOk,
      source_mode: sourceMode,
      content_sha256: contentHash,
      warnings,
    },
  };
}

async function main() {
  const { catalog, status } = await buildSnapshot();
  await Promise.all([
    fs.writeFile(new URL('./catalog.json', import.meta.url), `${JSON.stringify(catalog, null, 2)}\n`),
    fs.writeFile(new URL('./status.json', import.meta.url), `${JSON.stringify(status, null, 2)}\n`),
  ]);
  console.log(JSON.stringify(status, null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(`KEY refresh failed: ${error.stack || error.message}`);
    process.exitCode = 1;
  });
}
