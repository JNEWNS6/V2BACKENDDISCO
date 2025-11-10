CREATE TABLE IF NOT EXISTS retailer_profiles (
  id SERIAL PRIMARY KEY,
  domain TEXT NOT NULL UNIQUE,
  retailer_name TEXT NOT NULL,
  active BOOLEAN DEFAULT TRUE,
  selectors TEXT DEFAULT '{}',
  heuristics TEXT DEFAULT '{}',
  metadata TEXT DEFAULT '{}',
  last_synced TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_retailer_profiles_active ON retailer_profiles(active);
CREATE INDEX IF NOT EXISTS idx_retailer_profiles_synced ON retailer_profiles(last_synced);

CREATE TABLE IF NOT EXISTS retailer_inventory (
  id BIGSERIAL PRIMARY KEY,
  retailer_id INTEGER NOT NULL REFERENCES retailer_profiles(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  source TEXT,
  tags TEXT DEFAULT '[]',
  attributes TEXT DEFAULT '{}',
  first_seen TIMESTAMPTZ DEFAULT NOW(),
  last_seen TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  UNIQUE(retailer_id, code)
);
CREATE INDEX IF NOT EXISTS idx_retailer_inventory_retailer ON retailer_inventory(retailer_id);
CREATE INDEX IF NOT EXISTS idx_retailer_inventory_last_seen ON retailer_inventory(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_retailer_inventory_expires ON retailer_inventory(expires_at);
