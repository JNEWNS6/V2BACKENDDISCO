// queue.js
import pkg from 'bullmq';
const { Queue, Worker } = pkg; // ⬅️ no QueueScheduler in v5
import IORedis from 'ioredis';
import { Pool } from 'pg';
import { verifyPromo } from './utils/verifyPromo.js';

// TLS if rediss://
const isTLS = process.env.REDIS_URL?.startsWith('rediss://');

const connection = new IORedis(process.env.REDIS_URL, {
  maxRetriesPerRequest: null,
  enableReadyCheck: false,
  ...(isTLS ? { tls: { rejectUnauthorized: false } } : {}),
});

// Queues
export const promoQueue = new Queue('promoVerification', { connection });
export const billingQueue = new Queue('billingOps', { connection });

// Postgres
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
});

// Workers
new Worker(
  'promoVerification',
  async job => {
    const { domain, code } = job.data;
    const result = await verifyPromo(domain, code);
    return { domain, code, ...result };
  },
  { connection }
);

new Worker(
  'billingOps',
  async job => {
    if (job.name === 'deactivateOfferAfterGrace') {
      const { offerId } = job.data;
      const { rows } = await pool.query(
        'SELECT billing_suspended_at, active FROM offers WHERE id=$1',
        [offerId]
      );
      const rec = rows[0];
      if (rec?.active && rec?.billing_suspended_at) {
        await pool.query('UPDATE offers SET active=false, paid=false WHERE id=$1', [offerId]);
        return { offerId, deactivated: true };
      }
      return { offerId, deactivated: false };
    }
    return { ok: true };
  },
  { connection }
);

// Helper
export async function scheduleDeactivation(offerId, delayMs) {
  return billingQueue.add(
    'deactivateOfferAfterGrace',
    { offerId },
    { delay: delayMs, removeOnComplete: true, removeOnFail: true }
  );
}
