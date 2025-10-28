CREATE TABLE IF NOT EXISTS promos (
  id SERIAL PRIMARY KEY,
  domain TEXT NOT NULL,
  code TEXT NOT NULL,
  discount_percent INT,
  description TEXT,
  expires DATE,
  valid BOOLEAN DEFAULT true,
  UNIQUE(domain, code)
);