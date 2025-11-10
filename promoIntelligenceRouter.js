import express from 'express';
import rateLimit from 'express-rate-limit';
import crypto from 'crypto';
import { pool } from './db.js';
import { runScraperOp } from './utils/pythonCli.js';

const router = express.Router();
const suggestLimiter = rateLimit({ windowMs: 60_000, max: 60 });
const rankLimiter = rateLimit({ windowMs: 60_000, max: 120 });
const eventLimiter = rateLimit({ windowMs: 60_000, max: 240 });

const RETENTION_DAYS = Number(process.env.CODE_EVENT_RETENTION_DAYS || 180);
const PRUNE_INTERVAL_MS = 60 * 60 * 1000; // hourly
let lastPrune = 0;

function normalizeDomain(domain) {
  return String(domain || '')
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '');
}

function normalizeCode(code) {
  return String(code || '')
    .trim()
    .toUpperCase();
}

function parseJSON(value, fallback) {
  if (!value) return fallback;
  if (typeof value === 'object') return value;
  try {
    return JSON.parse(value);
  } catch (err) {
    return fallback;
  }
}

function clampLimit(value, fallback, max = 50) {
  const num = Number.parseInt(value, 10);
  if (!Number.isFinite(num) || num <= 0) return fallback;
  return Math.min(num, max);
}

function roundCurrency(value) {
  if (value === null || value === undefined) return null;
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  return Math.round(num * 100) / 100;
}

function hashAnonId(anonId) {
  if (!anonId) return null;
  return crypto.createHash('sha256').update(String(anonId)).digest('hex');
}

async function pruneOldEvents() {
  if (!RETENTION_DAYS || RETENTION_DAYS <= 0) {
    return;
  }
  const now = Date.now();
  if (now - lastPrune < PRUNE_INTERVAL_MS) {
    return;
  }
  lastPrune = now;
  const window = `${RETENTION_DAYS} days`;
  try {
    await pool.query(
      `DELETE FROM code_attempts WHERE created_at < NOW() - INTERVAL '${window}'`
    );
  } catch (err) {
    console.error('Failed to prune code_attempts:', err.message);
  }
}

async function fetchSeeds(domain, limit) {
  const { rows } = await pool.query(
    `SELECT code, source, created_at FROM code_seeds
     WHERE domain=$1
     ORDER BY created_at DESC
     LIMIT $2`,
    [domain, limit]
  );
  return rows.map(row => ({ code: normalizeCode(row.code), source: row.source || 'seed' }));
}

async function fetchRecentSuccess(domain, limit) {
  const { rows } = await pool.query(
    `SELECT code, saved, created_at FROM code_attempts
     WHERE domain=$1 AND success=true
     ORDER BY created_at DESC
     LIMIT $2`,
    [domain, limit]
  );
  return rows.map(row => ({
    code: normalizeCode(row.code),
    source: 'success',
    metadata: {
      saved: Number(row.saved || 0),
      seenAt: row.created_at ? new Date(row.created_at).toISOString() : null,
    },
  }));
}

async function fetchScraped(domain, url, html, limit) {
  const { codes = [], error } = await runScraperOp('codes', {
    domain,
    url,
    html,
    limit,
  });
  if (error) {
    throw new Error(error);
  }
  return codes
    .map(entry =>
      typeof entry === 'string'
        ? { code: normalizeCode(entry), source: 'scrape' }
        : {
            code: normalizeCode(entry.code),
            source: 'scrape',
            metadata: entry,
          }
    )
    .filter(item => !!item.code);
}

async function fetchCatalogInventory(domain, limit) {
  const { rows } = await pool.query(
    `SELECT i.code, i.source, i.tags, i.attributes, i.last_seen, i.expires_at
       FROM retailer_inventory i
       JOIN retailer_profiles r ON r.id = i.retailer_id
      WHERE r.domain=$1 AND r.active=true
      ORDER BY i.last_seen DESC
      LIMIT $2`,
    [domain, limit]
  );
  return rows
    .map(row => ({
      code: normalizeCode(row.code),
      source: row.source || 'catalog',
      metadata: {
        tags: Array.isArray(row.tags) ? row.tags : parseJSON(row.tags, []),
        attributes:
          row.attributes && typeof row.attributes === 'object'
            ? row.attributes
            : parseJSON(row.attributes, {}),
        lastSeen: row.last_seen ? new Date(row.last_seen).toISOString() : null,
        expiresAt: row.expires_at ? new Date(row.expires_at).toISOString() : null,
      },
    }))
    .filter(item => !!item.code);
}

function mergeCandidates(limit, ...lists) {
  const merged = [];
  const seen = new Set();
  for (const list of lists) {
    for (const item of list) {
      const code = item.code;
      if (!code || seen.has(code)) continue;
      merged.push({
        code,
        source: item.source,
        metadata: item.metadata || {},
      });
      seen.add(code);
      if (merged.length >= limit) {
        return merged;
      }
    }
  }
  return merged;
}

router.post('/suggest', suggestLimiter, async (req, res) => {
  const domain = normalizeDomain(req.body?.domain);
  const limit = clampLimit(req.body?.limit, 25, 50);
  const url = req.body?.url ? String(req.body.url) : undefined;
  const html = req.body?.html ? String(req.body.html) : undefined;

  if (!domain) {
    return res.status(400).json({ error: 'domain required' });
  }

  try {
    await pruneOldEvents();

    const [inventory, successes, scraped, seeds] = await Promise.all([
      fetchCatalogInventory(domain, limit),
      fetchRecentSuccess(domain, limit),
      fetchScraped(domain, url, html, limit),
      fetchSeeds(domain, limit),
    ]);

    const merged = mergeCandidates(limit, inventory, successes, scraped, seeds);
    res.json({
      domain,
      limit,
      generatedAt: new Date().toISOString(),
      codes: merged.map(item => ({
        code: item.code,
        source: item.source,
        metadata: item.metadata,
      })),
    });
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

router.post('/rank', rankLimiter, async (req, res) => {
  const domain = normalizeDomain(req.body?.domain);
  const codes = Array.isArray(req.body?.codes) ? req.body.codes : [];
  if (!domain) {
    return res.status(400).json({ error: 'domain required' });
  }
  if (!codes.length) {
    return res.status(400).json({ error: 'codes required' });
  }
  const normalizedCodes = codes
    .map(normalizeCode)
    .filter(Boolean);
  if (!normalizedCodes.length) {
    return res.status(400).json({ error: 'codes required' });
  }

  try {
    const { ranked = [], error } = await runScraperOp('rank', {
      domain,
      candidates: normalizedCodes,
    });
    if (error) {
      return res.status(502).json({ error });
    }
    res.json({
      domain,
      generatedAt: new Date().toISOString(),
      rankings: ranked.map(item => {
        const meta = item.meta || {};
        const score = typeof item.score === 'number' ? item.score : Number(item.score || 0);
        return {
          code: normalizeCode(item.code),
          score,
          predictedSavings: typeof meta.predicted_savings === 'number' ? meta.predicted_savings : null,
          confidence: typeof meta.confidence === 'number' ? meta.confidence : null,
          bestForCartTotal: typeof meta.best_for_total === 'number' ? meta.best_for_total : null,
          metadata: meta,
        };
      }),
    });
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

router.post('/event', eventLimiter, async (req, res) => {
  const optOutHeader = String(req.get('x-disco-opt-out') || '').toLowerCase();
  const requestedOptOut =
    optOutHeader === 'true' ||
    optOutHeader === '1' ||
    req.body?.opt_out ||
    req.body?.optOut;
  if (requestedOptOut) {
    return res.status(202).json({ ok: false, stored: false, reason: 'opt_out' });
  }

  const domain = normalizeDomain(req.body?.domain);
  const code = normalizeCode(req.body?.code);
  if (!domain || !code) {
    return res.status(400).json({ error: 'domain and code required' });
  }

  const success = Boolean(req.body?.success);
  const before = roundCurrency(req.body?.before_total);
  const after = roundCurrency(req.body?.after_total);
  let saved = roundCurrency(req.body?.saved);
  if (saved === null && before !== null && after !== null) {
    saved = roundCurrency(Math.max(0, before - after));
  }

  const anonId = hashAnonId(req.body?.anon_id || req.body?.anonId);
  const userAgent = String(req.get('user-agent') || '').slice(0, 255);

  try {
    await pruneOldEvents();
    await pool.query(
      `INSERT INTO code_attempts (domain, code, success, saved, before_total, after_total, user_agent, anon_id)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
      [domain, code, success, saved, before, after, userAgent || null, anonId]
    );
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

export default router;
