INSERT INTO users (full_name, email)
VALUES ('Default User', 'demo@reconcileai.test')
ON CONFLICT (email) DO NOTHING;