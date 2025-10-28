import express from 'express';
import rateLimit from 'express-rate-limit';
import { pool } from './db.js';
import { promoQueue, billingQueue } from './queue.js';

export function requireAdmin(req,res,next){
  const token = (req.headers.authorization||'').replace(/Bearer\s+/i,'');
  if (!process.env.ADMIN_TOKEN || token !== process.env.ADMIN_TOKEN) return res.status(401).json({ error:'unauthorized' });
  next();
}
const router = express.Router();
const limiter = rateLimit({ windowMs: 60_000, max: 100 });

router.get('/metrics/total-savings', requireAdmin, async (req,res)=>{
  const { rows } = await pool.query('SELECT COALESCE(SUM(est_savings),0) AS total FROM promo_savings');
  res.json({ total: Number(rows[0]?.total || 0) });
});

router.get('/metrics/user-total', requireAdmin, async (req,res)=>{
  const anon = String(req.query.anon_id||'');
  if (!anon) return res.status(400).json({ error:'missing anon_id' });
  const { rows } = await pool.query('SELECT COALESCE(SUM(est_savings),0) AS total FROM promo_savings WHERE anon_id=$1', [anon]);
  res.json({ anon_id: anon, total: Number(rows[0]?.total || 0) });
});

router.get('/queues/summary', requireAdmin, async (req,res)=>{
  const [promo, billing] = await Promise.all([ promoQueue.getJobCounts(), billingQueue.getJobCounts() ]);
  res.json({ promo, billing });
});

router.get('/offers', requireAdmin, async (req,res)=>{
  const { rows } = await pool.query('SELECT * FROM offers ORDER BY active DESC, expires NULLS LAST, id');
  res.json(rows);
});

router.post('/offers', requireAdmin, express.json(), async (req,res)=>{
  const o = req.body || {};
  const sql = `INSERT INTO offers (id, active, paid, trial_until, domains, countries, sponsor, title, cta, url, disclosure, expires, sponsor_contact, invoice_status)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
               ON CONFLICT (id) DO UPDATE SET active=EXCLUDED.active, paid=EXCLUDED.paid, trial_until=EXCLUDED.trial_until, domains=EXCLUDED.domains, countries=EXCLUDED.countries,
                 sponsor=EXCLUDED.sponsor, title=EXCLUDED.title, cta=EXCLUDED.cta, url=EXCLUDED.url, disclosure=EXCLUDED.disclosure, expires=EXCLUDED.expires, sponsor_contact=EXCLUDED.sponsor_contact, invoice_status=EXCLUDED.invoice_status`;
  await pool.query(sql, [o.id, !!o.active, !!o.paid, o.trial_until||null, o.domains||[], o.countries||null, o.sponsor, o.title, o.cta||'Activate', o.url, o.disclosure||null, o.expires||null, o.sponsor_contact||null, o.invoice_status||null]);
  res.json({ ok:true, id: o.id });
});

router.put('/offers/:id', requireAdmin, express.json(), async (req,res)=>{
  const id = req.params.id;
  const o = req.body || {};
  const sql = `UPDATE offers SET
      active=COALESCE($2, active), paid=COALESCE($3, paid), trial_until=COALESCE($4, trial_until),
      domains=COALESCE($5, domains), countries=COALESCE($6, countries), sponsor=COALESCE($7, sponsor),
      title=COALESCE($8, title), cta=COALESCE($9, cta), url=COALESCE($10, url), disclosure=COALESCE($11, disclosure),
      expires=COALESCE($12, expires), sponsor_contact=COALESCE($13, sponsor_contact), invoice_status=COALESCE($14, invoice_status)
    WHERE id=$1`;
  await pool.query(sql, [id, o.active, o.paid, o.trial_until, o.domains, o.countries, o.sponsor, o.title, o.cta, o.url, o.disclosure, o.expires, o.sponsor_contact, o.invoice_status ]);
  res.json({ ok:true });
});

export default router;