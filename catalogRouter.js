import express from 'express';
import rateLimit from 'express-rate-limit';
import { pool } from './db.js';

const router = express.Router();
const coverageLimiter = rateLimit({ windowMs: 60_000, max: 60 });
const detailLimiter = rateLimit({ windowMs: 60_000, max: 120 });

function normalizeDomain(domain) {
  return String(domain || '')
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '');
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

router.get('/catalog/coverage', coverageLimiter, async (_req, res) => {
  try {
    const { rows } = await pool.query(
      `SELECT r.domain, r.retailer_name, r.last_synced, r.metadata, r.active,
              COUNT(i.id) AS inventory_count
         FROM retailer_profiles r
    LEFT JOIN retailer_inventory i ON i.retailer_id = r.id
        WHERE r.active = true
     GROUP BY r.id
     ORDER BY r.domain ASC`
    );
    const retailers = rows.map(row => {
      const metadata = parseJSON(row.metadata, {});
      return {
        domain: row.domain,
        retailer: row.retailer_name,
        platform: metadata?.platform || 'generic',
        aliases: metadata?.aliases || [],
        regions: metadata?.regions || [],
        inventory: Number(row.inventory_count || 0),
        last_synced: row.last_synced ? new Date(row.last_synced).toISOString() : null,
      };
    });
    res.json({
      total: retailers.length,
      generated_at: new Date().toISOString(),
      retailers,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.get('/catalog/:domain', detailLimiter, async (req, res) => {
  const domain = normalizeDomain(req.params.domain);
  if (!domain) {
    return res.status(400).json({ error: 'domain required' });
  }
  try {
    const { rows } = await pool.query(
      `SELECT id, domain, retailer_name, selectors, heuristics, metadata, last_synced
         FROM retailer_profiles
        WHERE domain = $1 AND active = true
        LIMIT 1`,
      [domain]
    );
    const profile = rows[0];
    if (!profile) {
      return res.status(404).json({ error: 'catalog entry not found' });
    }
    const selectors = parseJSON(profile.selectors, {});
    const heuristics = parseJSON(profile.heuristics, {});
    const metadata = parseJSON(profile.metadata, {});
    const { rows: inventoryRows } = await pool.query(
      `SELECT code, source, tags, attributes, first_seen, last_seen, expires_at
         FROM retailer_inventory
        WHERE retailer_id = $1
        ORDER BY last_seen DESC
        LIMIT 1000`,
      [profile.id]
    );
    const inventory = inventoryRows.map(row => ({
      code: row.code,
      source: row.source || 'catalog',
      tags: Array.isArray(row.tags) ? row.tags : parseJSON(row.tags, []),
      attributes:
        row.attributes && typeof row.attributes === 'object'
          ? row.attributes
          : parseJSON(row.attributes, {}),
      first_seen: row.first_seen ? new Date(row.first_seen).toISOString() : null,
      last_seen: row.last_seen ? new Date(row.last_seen).toISOString() : null,
      expires_at: row.expires_at ? new Date(row.expires_at).toISOString() : null,
    }));
    res.json({
      domain: profile.domain,
      retailer: profile.retailer_name,
      platform: metadata?.platform || 'generic',
      checkout_hints: metadata?.checkout_hints || [],
      selectors,
      heuristics,
      scrape: metadata?.scrape || {},
      regions: metadata?.regions || [],
      aliases: metadata?.aliases || [],
      inventory,
      inventory_count: inventory.length,
      last_synced: profile.last_synced ? new Date(profile.last_synced).toISOString() : null,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

export default router;
