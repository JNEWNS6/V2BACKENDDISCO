INSERT INTO offers (id, active, paid, trial_until, domains, countries, sponsor, title, cta, url, disclosure, expires) VALUES
('snowdome_offer', true, false, NOW() + INTERVAL '14 days', ARRAY['snowdome.co.uk'], ARRAY['GB'], 'TravelDeals', '10% off ski passes', 'Book now', 'https://affiliate.example/snowdome?src=disco', 'Sponsored offer', '2025-11-30')
ON CONFLICT (id) DO NOTHING;