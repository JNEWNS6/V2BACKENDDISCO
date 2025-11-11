CREATE TABLE IF NOT EXISTS code_seeds (
  id SERIAL PRIMARY KEY,
  domain TEXT NOT NULL,
  code TEXT NOT NULL,
  source TEXT DEFAULT 'seed',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(domain, code)
);
CREATE INDEX IF NOT EXISTS idx_code_seeds_domain ON code_seeds(domain);

CREATE TABLE IF NOT EXISTS code_attempts (
  id BIGSERIAL PRIMARY KEY,
  domain TEXT NOT NULL,
  code TEXT NOT NULL,
  success BOOLEAN DEFAULT FALSE,
  saved NUMERIC(10,2) DEFAULT 0,
  before_total NUMERIC(10,2),
  after_total NUMERIC(10,2),
  user_agent TEXT,
  anon_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_code_attempts_domain_code ON code_attempts(domain, code);
CREATE INDEX IF NOT EXISTS idx_code_attempts_created ON code_attempts(created_at);

CREATE TABLE IF NOT EXISTS scrape_cache (
  id BIGSERIAL PRIMARY KEY,
  domain TEXT NOT NULL,
  url TEXT,
  codes_json TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(domain, url)
);
CREATE INDEX IF NOT EXISTS idx_scrape_cache_domain ON scrape_cache(domain);
