CREATE TABLE IF NOT EXISTS ad_events (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  anon_id TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('impression','click')),
  offer_id TEXT,
  domain TEXT
);
CREATE INDEX IF NOT EXISTS idx_ad_events_offer ON ad_events(offer_id);