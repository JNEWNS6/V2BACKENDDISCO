import express from 'express';
import { pool } from './db.js';

const router = express.Router();

router.get('/codes', async (req, res) => {
  try {
    const domain = String(req.query.domain || '').toLowerCase().replace(/^www\./,'');
    const limit = parseInt(req.query.limit || '10', 10);
    if (!domain) return res.status(400).json({ error: 'domain required' });
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
    const { rows } = await pool.query(
      `SELECT code, score, source, last_seen FROM codes
        WHERE domain=$1
        ORDER BY score DESC NULLS LAST, last_seen DESC
        LIMIT $2`, [domain, limit]);
    res.json({ domain, codes: rows, cached: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

export default router;
