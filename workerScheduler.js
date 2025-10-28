import { pool } from './db.js';
import { spawn } from 'child_process';
import fs from 'fs';

let schedule = null;
try {
  const raw = fs.readFileSync('adapters/schedule.json','utf8');
  schedule = JSON.parse(raw);
} catch (e) {
  schedule = null;
}

const FALLBACK_ALLOWLIST = (process.env.ALLOWLIST_DOMAINS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
const LIMIT = Number(process.env.SCRAPE_LIMIT || (schedule?.limit_per_run ?? 50));
const PER_DOMAIN_DELAY_MS = Number(process.env.SCRAPE_DELAY_MS || (schedule?.per_domain_delay_ms ?? 7000));

function runPython(op, jsonPayload) {
  return new Promise((resolve, reject) => {
    const proc = spawn(process.env.PYTHON_BIN || 'python3', ['scrape_cli.py', op], {
      cwd: process.cwd(),
      env: process.env,
    });
    let out = ''; let err = '';
    proc.stdout.on('data', d => out += d.toString());
    proc.stderr.on('data', d => err += d.toString());
    proc.on('error', reject);
    proc.on('close', code => {
      if (code === 0) {
        try { resolve(JSON.parse(out || '{}')); }
        catch (e) { reject(new Error('Invalid JSON from scraper: ' + e.message + '\n' + out)); }
      } else {
        resolve({ error: err || out || `exit ${code}` });
      }
    });
    proc.stdin.write(JSON.stringify(jsonPayload || {}));
    proc.stdin.end();
  });
}

async function upsertCodes(domain, codes) {
  if (!codes || !codes.length) return;
  await pool.query(`
    CREATE TABLE IF NOT EXISTS codes (
      id SERIAL PRIMARY KEY,
      domain TEXT NOT NULL,
      code TEXT NOT NULL,
      source TEXT,
      score DOUBLE PRECISION DEFAULT 0,
      valid_until TIMESTAMP NULL,
      created_at TIMESTAMP DEFAULT now(),
      last_seen TIMESTAMP DEFAULT now(),
      UNIQUE(domain, code)
    );
    CREATE INDEX IF NOT EXISTS idx_codes_domain ON codes(domain);
  `);
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    for (const item of codes) {
      const code = typeof item === 'string' ? item : item.code;
      const score = typeof item === 'string' ? null : (item.score ?? null);
      const source = typeof item === 'string' ? 'scrape' : (item.source ?? 'scrape');
      await client.query(
        `INSERT INTO codes (domain, code, source, score)
           VALUES ($1,$2,$3,$4)
         ON CONFLICT (domain, code)
         DO UPDATE SET last_seen=now(), score=COALESCE(EXCLUDED.score, codes.score)`,
        [domain, code, source, score]
      );
    }
    await client.query('COMMIT');
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

async function scrapeDomain(domain) {
  const { codes = [], error } = await runPython('codes', { domain, limit: LIMIT });
  if (error) {
    console.warn('[worker] scrape error', domain, error);
    return;
  }
  let ranked = codes;
  const rankRes = await runPython('rank', { domain, candidates: codes });
  if (rankRes && Array.isArray(rankRes.ranked) && rankRes.ranked.length) {
    ranked = rankRes.ranked.map(r => r.code);
  }
  await upsertCodes(domain, ranked);
  console.log(`[worker] updated ${domain}: ${ranked.length} codes`);
}

async function runTier(domains) {
  for (const d of domains) {
    await scrapeDomain(d);
    await new Promise(r => setTimeout(r, PER_DOMAIN_DELAY_MS));
  }
}

function startScheduler() {
  if (schedule && schedule.tiers) {
    console.log('[worker] using tiered schedule from adapters/schedule.json');
    for (const [tierName, tier] of Object.entries(schedule.tiers)) {
      const domains = (tier.domains || []).map(s => s.toLowerCase());
      const interval = Number(tier.interval_ms || 0);
      if (!domains.length || !interval) continue;
      const run = () => runTier(domains).catch(e => console.error(`[worker] ${tierName} error`, e));
      run();
      setInterval(run, interval);
      console.log(`[worker] tier ${tierName}: ${domains.length} domains every ${interval/3600000}h`);
    }
  } else if (FALLBACK_ALLOWLIST.length) {
    console.log('[worker] schedule.json missing; falling back to ALLOWLIST_DOMAINS with 30m interval');
    const run = () => runTier(FALLBACK_ALLOWLIST).catch(e => console.error('[worker] fallback error', e));
    run();
    setInterval(run, 30*60*1000);
  } else {
    console.log('[worker] no schedule and no allowlist; nothing to do.');
  }
}

startScheduler();
