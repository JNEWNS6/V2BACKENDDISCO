CREATE TABLE IF NOT EXISTS promo_fail (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  anon_id TEXT NOT NULL,
  domain TEXT NOT NULL,
  code TEXT
);
CREATE INDEX IF NOT EXISTS idx_promo_fail_domain ON promo_fail(domain);