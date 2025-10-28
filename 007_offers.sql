CREATE TABLE IF NOT EXISTS offers (
  id TEXT PRIMARY KEY,
  active BOOLEAN DEFAULT true,
  paid BOOLEAN DEFAULT false,
  trial_until TIMESTAMPTZ,
  domains TEXT[],
  countries TEXT[],
  sponsor TEXT NOT NULL,
  title TEXT NOT NULL,
  cta TEXT NOT NULL,
  url TEXT NOT NULL,
  disclosure TEXT,
  expires DATE,
  sponsor_contact TEXT,
  invoice_status TEXT,
  billing_suspended_at TIMESTAMPTZ,
  billing_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_offers_active ON offers(active);