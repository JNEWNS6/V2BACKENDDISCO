import { Pool } from 'pg';

const connectionString = process.env.DATABASE_URL;

const sslPreference = process.env.DATABASE_SSL?.toLowerCase();

let needsSSL = false;
if (sslPreference === 'true') {
  needsSSL = true;
} else if (sslPreference === 'false') {
  needsSSL = false;
} else {
  needsSSL =
    !!connectionString &&
    !connectionString.includes('localhost') &&
    !connectionString.includes('127.0.0.1');
}

export const pool = new Pool({
  connectionString,
  ...(needsSSL ? { ssl: { rejectUnauthorized: false } } : {}),
});
