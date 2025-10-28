INSERT INTO offers (id, active, paid, trial_until, domains, countries, sponsor, title, cta, url, disclosure, expires)
VALUES
('boots_cashback', true, true, NULL, ARRAY['boots.com'], ARRAY['GB'], 'CashbackWorld', 'Extra 5% cashback at Boots', 'Activate', 'https://affiliate.example/boots?src=disco', 'Affiliate link', '2025-12-31')
ON CONFLICT (id) DO NOTHING;