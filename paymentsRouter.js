import express from 'express';
import { stripe, successUrl, cancelUrl } from './stripe.js';
import { Pool } from 'pg';
import bodyParser from 'body-parser';
import { scheduleDeactivation } from './queue.js';
const router = express.Router();
const pool = new Pool({ connectionString: process.env.DATABASE_URL });

router.post('/stripe/webhook', bodyParser.raw({ type: 'application/json' }), async (req,res)=>{
  let event;
  try {
    const sig = req.headers['stripe-signature'];
    event = stripe.webhooks.constructEvent(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    return res.status(400).send('Invalid signature');
  }
  try {
    const type = event.type;
    const obj = event.data.object;
    let offerId = obj?.metadata?.offer_id || obj?.subscription?.metadata?.offer_id || null;
    if (!offerId && (type === 'invoice.payment_succeeded' || type === 'invoice.paid' || type === 'invoice.payment_failed')) {
      if (obj.subscription) {
        const sub = await stripe.subscriptions.retrieve(obj.subscription);
        offerId = sub?.metadata?.offer_id || null;
        if (!obj.status && sub.status) obj.status = sub.status;
      }
    }
    const successTypes = new Set(['checkout.session.completed','invoice.payment_succeeded','invoice.paid']);
    if (offerId && successTypes.has(type)) {
      await pool.query(`UPDATE offers SET paid=true, active=true, invoice_status='paid', billing_suspended_at=NULL, billing_reason=NULL WHERE id=$1`, [offerId]);
    }
    const failureTypes = new Set(['invoice.payment_failed','customer.subscription.updated','customer.subscription.paused']);
    if (failureTypes.has(type)) {
      if (offerId) {
        const graceDays = Number(process.env.BILLING_GRACE_DAYS || 5);
        const now = new Date();
        await pool.query(`UPDATE offers SET invoice_status='unpaid', billing_suspended_at=$2, billing_reason='payment_failed' WHERE id=$1`, [offerId, now]);
        const status = obj.status || 'past_due';
        if (status === 'unpaid') {
          await pool.query(`UPDATE offers SET active=false, paid=false WHERE id=$1`, [offerId]);
        } else {
          await scheduleDeactivation(offerId, graceDays * 24 * 3600 * 1000);
        }
      }
    }
    res.json({ received: true });
  } catch (e) {
    console.error('webhook handler failed', e);
    res.status(500).send('Webhook error');
  }
});

router.post('/sponsor/checkout', express.json(), async (req,res)=>{
  try {
    const { id, contactEmail, trialDays = 14 } = req.body || {};
    if (!id || !contactEmail) return res.status(400).json({ error: 'Missing id or contactEmail' });
    const trialUntil = (trialDays>0) ? new Date(Date.now()+trialDays*24*3600*1000) : null;
    await pool.query(
      `INSERT INTO offers (id, active, paid, trial_until, sponsor_contact, invoice_status)
       VALUES ($1,false,false,$2,$3,'unpaid')
       ON CONFLICT (id) DO UPDATE SET sponsor_contact=EXCLUDED.sponsor_contact`,
      [id, trialUntil, contactEmail]
    );
    const session = await stripe.checkout.sessions.create({
      mode: 'subscription',
      customer_email: contactEmail,
      line_items: [{ price: process.env.STRIPE_PRICE_ID, quantity: 1 }],
      success_url: successUrl(id),
      cancel_url: cancelUrl(id),
      metadata: { offer_id: id }
    });
    res.json({ checkout_url: session.url });
  } catch (e) {
    console.error('checkout error', e);
    res.status(500).json({ error: 'checkout_failed' });
  }
});

export default router;