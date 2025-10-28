CREATE TABLE IF NOT EXISTS promo_savings (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  anon_id TEXT NOT NULL,
  domain TEXT NOT NULL,
  code TEXT,
  discount_percent INT,
  est_savings NUMERIC(10,2)
);
CREATE INDEX IF NOT EXISTS idx_promo_savings_anon ON promo_savings(anon_id);