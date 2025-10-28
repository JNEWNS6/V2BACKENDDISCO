import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { Pool } from 'pg';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');

const connectionString = process.env.DATABASE_URL;
if (!connectionString) {
  console.error('DATABASE_URL is required to run migrations.');
  process.exit(1);
}

const sslPreference = process.env.DATABASE_SSL?.toLowerCase();

let needsSSL = false;
if (sslPreference === 'true') {
  needsSSL = true;
} else if (sslPreference === 'false') {
  needsSSL = false;
} else {
  needsSSL =
    !connectionString.includes('localhost') &&
    !connectionString.includes('127.0.0.1');
}

const pool = new Pool({
  connectionString,
  ...(needsSSL ? { ssl: { rejectUnauthorized: false } } : {}),
});

function loadMigrationFiles() {
  const candidates = [];
  for (const entry of fs.readdirSync(repoRoot)) {
    if (/^\d+_.*\.sql$/i.test(entry)) {
      candidates.push(path.join(repoRoot, entry));
    }
  }
  const migrationsDir = path.join(repoRoot, 'migrations');
  if (fs.existsSync(migrationsDir)) {
    for (const entry of fs.readdirSync(migrationsDir)) {
      if (/^\d+_.*\.sql$/i.test(entry)) {
        candidates.push(path.join(migrationsDir, entry));
      }
    }
  }
  return candidates.sort();
}

async function run() {
  const files = loadMigrationFiles();
  if (!files.length) {
    console.log('No migration files found.');
    await pool.end();
    return;
  }

  console.log(`Running ${files.length} migrations...`);
  for (const file of files) {
    const sql = fs.readFileSync(file, 'utf8');
    const name = path.basename(file);
    if (!sql.trim()) {
      console.log(`Skipping ${name} (empty file)`);
      continue;
    }
    console.log(`Applying ${name}...`);
    await pool.query(sql);
  }
  await pool.end();
  console.log('Migrations complete.');
}

run().catch(async err => {
  console.error('Migration failed:', err);
  await pool.end();
  process.exit(1);
});
