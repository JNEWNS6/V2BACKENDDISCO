# Run Disco Backend Locally

## 1) Install
```bash
cd backend/server
npm install
```

## 2) Environment
Copy `.env.example` to `.env` and edit values:
```bash
cp .env.example .env
```

## 3) Databases
Start Postgres & Redis, then run migrations:
```bash
createdb disco || true
for f in migrations/*.sql; do echo "Running $f"; psql "$DATABASE_URL" -f "$f"; done
redis-server
```

## 4) Start the server
```bash
npm run dev
```

Visit: http://localhost:3000/health
