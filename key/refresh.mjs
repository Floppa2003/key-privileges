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

function stripStringsAndComments(source) {
  let out = '';
  let state = 'code';
  let quote = '';

  for (let i = 0; i < source.length; i += 1) {
    const ch = source[i];
    const next = source[i + 1];

    if (state === 'code') {
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
      } else {
        out += ch;
      }
    } else if (state === 'string') {
      if (ch === '\\') {
        out += '  ';
        i += 1;
      } else if (ch === quote) {
        state = 'code';
        quote = '';
        out += ' ';
      } else {
        out += ch === '\n' ? '\n' : ' ';
      }
    } else if (state === 'line-comment') {
      if (ch === '\n') {
        state = 'code';
        out += '\n';
      } else {
        out += ' ';
      }
    } else if (state === 'block-comment') {
      if (ch === '*' && next === '/') {
        state = 'code';
        out += '  ';
        i += 1;
      } else {
        out += ch === '\n' ? '\n' : ' ';
      }
    }
  }

  return out;
}

export function extractBalancedLiteral(source, variableName) {
  const escaped = variableName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const assignment = new RegExp(`\\b(?:const|let|var)\\s+${escaped}\\s*=`, 'u');
  const match = assignment.exec(source);
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

    if (state === 'code') {
      if (ch === '"' || ch === "'" || ch === '`') {
        state = 'string';
        quote = ch;
        continue;
      }
      if (ch === '/' && next === '/') {
        state = 'line-comment';
        i += 1;
        continue;
      }
      if (ch === '/' && next === '*') {
        state = 'block-comment';
        i += 1;
        continue;
      }
      if (ch === opener) depth += 1;
      if (ch === closer) {
        depth -= 1;
        if (depth === 0) return source.slice(start, i + 1);
      }
    } else if (state === 'string') {
      if (ch === '\\') i += 1;
      else if (ch === quote) {
        state = 'code';
        quote = '';
      }
    } else if (state === 'line-comment') {
      if (ch === '\n') state = 'code';
    } else if (state === 'block-comment') {
      if (ch === '*' && next === '/') {
        state = 'code';
        i += 1;
      }
    }
  }

  throw new Error(`Unterminated literal for ${variableName}`);
}

function evaluateDataLiteral(literal, label) {
  const codeOnly = stripStringsAndComments(literal);
  const forbidden = /=>|\bfunction\b|\bnew\b|\bclass\b|\bawait\b|\byield\b|\bimport\b|\brequire\b|\bprocess\b|\bglobalThis\b|\bconstructor\b|__proto__|\bthis\b/u;
  if (forbidden.test(codeOnly)) throw new Error(`Executable construct rejected in ${label}`);

  const value = vm.runInNewContext(`(${literal})`, Object.create(null), {
    timeout: 250,
    displayErrors: true,
  });
  return JSON.parse(JSON.stringify(value));
}

export function parseAppData(source) {
  const partners = evaluateDataLiteral(extractBalancedLiteral(source, 'partners'), 'partners');
  const specialOffers = evaluateDataLiteral(extractBalancedLiteral(source, 'specialOffers'), 'specialOffers');

  if (!Array.isArray(partners)) throw new Error('partners is not an array');
  if (!specialOffers || typeof specialOffers !== 'object' || Array.isArray(specialOffers)) {
    throw new Error('specialOffers is not an object');
  }
  return { partners, specialOffers };
}

export function extractPartnerContentIds(source) {
  const marker = source.indexOf('PARTNER_CONTENT_IDS');
  if (marker < 0) return [];
  const open = source.indexOf('[', marker);
  if (open < 0) return [];

  const synthetic = `const ids = ${source.slice(open)}`;
  let literal;
  try {
    literal = extractBalancedLiteral(synthetic, 'ids');
  } catch {
    return [];
  }

  const ids = evaluateDataLiteral(literal, 'PARTNER_CONTENT_IDS');
  return Array.isArray(ids) && ids.every((value) => typeof value === 'string') ? ids : [];
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
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null;
  if (payload.ok === false) return null;
  if (payload.data && typeof payload.data === 'object' && payload.data.snapshot && typeof payload.data.snapshot === 'object') {
    return payload.data.snapshot;
  }
  if (payload.snapshot && typeof payload.snapshot === 'object') return payload.snapshot;
  if (payload.values && typeof payload.values === 'object') return payload;
  return null;
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

export function normalizePartners(basePartners, contentIds = [], remoteSnapshot = null) {
  return basePartners.map((partner, index) => {
    if (!partner || typeof partner !== 'object' || Array.isArray(partner)) {
      throw new Error(`Invalid partner at index ${index}`);
    }
    if (typeof partner.name !== 'string' || !partner.name.trim()) {
      throw new Error(`Partner ${index} has no name`);
    }

    const id = typeof partner.contentId === 'string' && partner.contentId
      ? partner.contentId
      : contentIds[index] || `partner-${index + 1}`;
    const field = (suffix) => `partners.cards.${id}.${suffix}`;

    const fallbackPerks = partner.perkCopyRu
      && typeof partner.perkCopyRu === 'object'
      && !Array.isArray(partner.perkCopyRu)
      && Array.isArray(partner.perkIds)
      ? partner.perkIds.map((perkId) => partner.perkCopyRu?.[perkId]).filter(Boolean)
      : Array.isArray(partner.perksRu) && partner.perksRu.length
        ? partner.perksRu
        : Array.isArray(partner.perks) ? partner.perks : [];

    const fallbackSummary = partner.editorial
      || partner.portfolioDescriptionRu
      || partner.portfolioDescription
      || '';
    const baseBrands = Array.isArray(partner.keyBrands)
      ? partner.keyBrands.filter((value) => typeof value === 'string')
      : [];

    const brandsText = remoteRu(remoteSnapshot, field('brands'), baseBrands.join(' · '));
    const perks = Array.from({ length: 8 }, (_, perkIndex) => (
      remoteRu(remoteSnapshot, field(`perk.${perkIndex + 1}`), fallbackPerks[perkIndex] || '')
    )).filter(Boolean);
    const favorites = Array.from({ length: 4 }, (_, itemIndex) => (
      remoteRu(remoteSnapshot, field(`favorite.${itemIndex + 1}`), partner.favorites?.[itemIndex] || '')
    )).filter(Boolean);
    const fresh = Array.from({ length: 4 }, (_, itemIndex) => (
      remoteRu(remoteSnapshot, field(`fresh.${itemIndex + 1}`), partner.fresh?.[itemIndex] || '')
    )).filter(Boolean);

    const candidateRemoteFields = [
      field('name'), field('hotel_count'), field('summary'), field('brands'), field('scope'), field('favorites_label'),
      ...Array.from({ length: 8 }, (_, perkIndex) => field(`perk.${perkIndex + 1}`)),
      ...Array.from({ length: 4 }, (_, itemIndex) => field(`favorite.${itemIndex + 1}`)),
      ...Array.from({ length: 4 }, (_, itemIndex) => field(`fresh.${itemIndex + 1}`)),
    ];
    const remoteApplied = Boolean(remoteSnapshot && candidateRemoteFields.some((fieldId) => (
      typeof remoteSnapshot?.values?.[fieldId]?.ru === 'string'
      && remoteSnapshot.values[fieldId].ru.trim()
    )));

    return {
      id,
      name: remoteRu(remoteSnapshot, field('name'), partner.name),
      logo: absoluteAsset(partner.logo),
      brands: baseBrands,
      brands_text: brandsText,
      hotel_count: remoteRu(remoteSnapshot, field('hotel_count'), partner.hotelCount || ''),
      summary: remoteRu(remoteSnapshot, field('summary'), fallbackSummary),
      scope: remoteRu(remoteSnapshot, field('scope'), partner.perkScope || ''),
      perks,
      favorites_label: remoteRu(remoteSnapshot, field('favorites_label'), partner.favoritesLabel || 'Любимые адреса'),
      favorites,
      fresh,
      source: {
        label: typeof partner.sourceLabel === 'string' ? partner.sourceLabel : '',
        url: typeof partner.sourceUrl === 'string' ? partner.sourceUrl : '',
        as_of: typeof partner.sourceAsOf === 'string' ? partner.sourceAsOf : '',
        conditions: typeof partner.sourceConditions === 'string' ? partner.sourceConditions : '',
      },
      remote_overrides_applied: remoteApplied,
    };
  });
}

async function fetchText(url, headers = {}) {
  const response = await fetch(url, {
    method: 'GET',
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
  if (Number.isFinite(declaredLength) && declaredLength > MAX_TEXT_BYTES) {
    throw new Error(`${url} response too large`);
  }

  const text = await response.text();
  if (Buffer.byteLength(text) > MAX_TEXT_BYTES) throw new Error(`${url} response too large`);
  return text;
}

async function fetchJson(url, headers = {}) {
  const text = await fetchText(url, { Accept: 'application/json', ...headers });
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${url} returned invalid JSON`);
  }
}

async function tryRemoteSnapshot(warnings) {
  let anonKey = '';
  try {
    const configSource = await fetchText(SUPABASE_CONFIG_URL);
    anonKey = extractSupabaseAnonKey(configSource);
    if (!anonKey) {
      warnings.push('Supabase anon key was not found in public app config; trying endpoint without it.');
    }
  } catch (error) {
    warnings.push(`Could not read public Supabase config: ${error.message}`);
  }

  try {
    const payload = await fetchJson(MINIAPP_CONTENT_URL, anonKey ? { apikey: anonKey } : {});
    const snapshot = extractRemoteSnapshot(payload);
    if (!snapshot) throw new Error('response did not contain a recognizable snapshot');
    return { snapshot, ok: true };
  } catch (error) {
    warnings.push(`Supabase content override unavailable: ${error.message}`);
    return { snapshot: null, ok: false };
  }
}

function stableHash(value) {
  return crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

async function requestIdForEvent() {
  const event = process.env.GITHUB_EVENT_NAME || 'local';
  if (event !== 'push') return null;

  try {
    const trigger = JSON.parse(await fs.readFile(new URL('./trigger.json', import.meta.url), 'utf8'));
    return typeof trigger.request_id === 'string' && trigger.request_id ? trigger.request_id : null;
  } catch {
    return null;
  }
}

export async function buildSnapshot() {
  const warnings = [];
  const fetchedAt = new Date().toISOString();

  const dataSource = await fetchText(DATA_URL);
  const { partners: basePartners, specialOffers } = parseAppData(dataSource);
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
  const canApplyRemote = remote.ok && contentIds.length === basePartners.length;
  const normalized = normalizePartners(basePartners, contentIds, canApplyRemote ? remote.snapshot : null);
  const special = {
    ru: Array.isArray(specialOffers.ru) ? specialOffers.ru.filter((value) => typeof value === 'string') : [],
    en: Array.isArray(specialOffers.en) ? specialOffers.en.filter((value) => typeof value === 'string') : [],
  };

  const contentCore = { partners: normalized, special_offers: special };
  const contentHash = stableHash(contentCore);
  const requestId = await requestIdForEvent();

  const catalog = {
    schema_version: 1,
    fetched_at: fetchedAt,
    source_mode: canApplyRemote ? 'netlify+supabase' : 'netlify',
    remote_ok: canApplyRemote,
    source_urls: {
      base_catalog: DATA_URL,
      content_contract: CONTRACT_URL,
      remote_content: MINIAPP_CONTENT_URL,
    },
    remote_snapshot: canApplyRemote ? {
      version: remote.snapshot?.version ?? null,
      published_at: remote.snapshot?.published_at ?? remote.snapshot?.publishedAt ?? null,
      schema_version: remote.snapshot?.schema_version ?? null,
    } : null,
    content_sha256: contentHash,
    ...contentCore,
  };

  const status = {
    schema_version: 1,
    ok: true,
    fetched_at: fetchedAt,
    request_id: requestId,
    triggered_by: process.env.GITHUB_EVENT_NAME || 'local',
    partner_count: normalized.length,
    special_offer_count: special.ru.length,
    remote_ok: canApplyRemote,
    source_mode: catalog.source_mode,
    content_sha256: contentHash,
    warnings,
  };

  return { catalog, status };
}

async function main() {
  const { catalog, status } = await buildSnapshot();
  await fs.writeFile(new URL('./catalog.json', import.meta.url), `${JSON.stringify(catalog, null, 2)}\n`);
  await fs.writeFile(new URL('./status.json', import.meta.url), `${JSON.stringify(status, null, 2)}\n`);
  console.log(JSON.stringify(status, null, 2));
}

const invoked = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (invoked) {
  main().catch((error) => {
    console.error(`KEY refresh failed: ${error.stack || error.message}`);
    process.exitCode = 1;
  });
}
