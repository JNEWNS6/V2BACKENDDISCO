import express from 'express';
import cors from 'cors';
import bodyParser from 'body-parser';
import path from 'path';
import { fileURLToPath } from 'url';
import eventsRouter from './eventsRouter.js';
import adminRouter, { requireAdmin } from './adminRouter.js';
import paymentsRouter from './paymentsRouter.js';
import publicCodesRouter from './publicCodesRouter.js';
if (process.env.START_QUEUE_IN_WEB !== 'false') {
  await import('./queue.js');
}

const app = express();

app.use('/', publicCodesRouter);

app.use(cors());
app.use(bodyParser.json({ limit: '1mb' }));

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

app.use('/api', eventsRouter);
app.use('/api', paymentsRouter);
app.use('/api/admin', adminRouter);

app.use(express.static(path.join(__dirname, 'public')));
app.get('/admin', (req, res) =>
  res.sendFile(path.join(__dirname, 'public', 'admin.html'))
);
app.get('/admin/offers', (req, res) =>
  res.sendFile(path.join(__dirname, 'public', 'admin_offers.html'))
);

app.get('/health', (req, res) => res.json({ ok: true }));
app.get('/', (req, res) => {
  res.send('Disco backend is running. Try <a href="/health">/health</a> or <a href="/admin">/admin</a>.');
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log('DISCO API listening on', port));
