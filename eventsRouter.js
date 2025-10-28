import express from 'express';
import rateLimit from 'express-rate-limit';
import { pool } from './db.js';

const router = express.Router();
const limiter = rateLimit({ windowMs: 60_000, max: 100 });

router.post('/events/success', limiter, express.json(), async (req,res)=>{
  const { anon_id, domain, code, discount_percent, est_savings, ts } = req.body || {};
  await pool.query(`INSERT INTO promo_savings (ts, anon_id, domain, code, discount_percent, est_savings)
                    VALUES ($1,$2,$3,$4,$5,$6)`,
                    [ts?new Date(ts):new Date(), anon_id, domain, code, discount_percent||null, est_savings||null]);
  res.json({ ok:true });
});

router.post('/events/fail', limiter, express.json(), async (req,res)=>{
  const { anon_id, domain, code, ts } = req.body || {};
  await pool.query(`INSERT INTO promo_fail (ts, anon_id, domain, code) VALUES ($1,$2,$3,$4)`,
                    [ts?new Date(ts):new Date(), anon_id, domain, code]);
  res.json({ ok:true });
});

router.post('/events/savings', limiter, express.json(), async (req,res)=>{
  const { anon_id, domain, code, est_savings, ts } = req.body || {};
  await pool.query(`INSERT INTO promo_savings (ts, anon_id, domain, code, est_savings) VALUES ($1,$2,$3,$4,$5)`,
                    [ts?new Date(ts):new Date(), anon_id, domain, code, est_savings||null]);
  res.json({ ok:true });
});

router.post('/events/ad-impression', limiter, express.json(), async (req,res)=>{
  const { anon_id, offer_id, domain, ts } = req.body || {};
  await pool.query(`INSERT INTO ad_events (ts, anon_id, event_type, offer_id, domain) VALUES ($1,$2,'impression',$3,$4)`,
                    [ts?new Date(ts):new Date(), anon_id, offer_id||null, domain||null]);
  res.json({ ok:true });
});

router.post('/events/ad-click', limiter, express.json(), async (req,res)=>{
  const { anon_id, offer_id, domain, ts } = req.body || {};
  await pool.query(`INSERT INTO ad_events (ts, anon_id, event_type, offer_id, domain) VALUES ($1,$2,'click',$3,$4)`,
                    [ts?new Date(ts):new Date(), anon_id, offer_id||null, domain||null]);
  res.json({ ok:true });
});

router.get('/promos/:domain', async (req,res)=>{
  const domain = String(req.params.domain||'').toLowerCase();
  const { rows } = await pool.query('SELECT code, discount_percent, description, expires FROM promos WHERE domain=$1 ORDER BY discount_percent DESC NULLS LAST LIMIT 10', [domain]);
  res.json({ domain, promos: rows });
});

router.get('/offers', async (req,res)=>{
  const { domain = '', country = null } = req.query;
  const { rows } = await pool.query(`
    SELECT * FROM offers
     WHERE active = true
       AND (paid = true OR (trial_until IS NOT NULL AND trial_until > NOW()))
       AND ($1 = '' OR $1 = ANY(domains))
       AND ($2::text IS NULL OR countries IS NULL OR $2 = ANY(countries))
     ORDER BY COALESCE(expires, NOW() + INTERVAL '365 days') ASC
     LIMIT 1
  `, [String(domain).toLowerCase(), country || null]);
  res.json({ offers: rows });
});

export default router;