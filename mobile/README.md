# Cards — mobile app

Expo (SDK 58) + React Native + TypeScript. Offline-first: the blitz lives in a
local SQLite database and syncs with the Django API (`/api/`) when online.

## Run on a phone (development)

Easiest — from the repo root, with Docker (server + Expo, QR code in the logs):
```bash
LAN_IP=<your-LAN-IP> DJANGO_ALLOWED_HOSTS=localhost,<your-LAN-IP> docker compose --profile mobile up
```

Without Docker:

1. Start Django so the phone can reach it (same Wi-Fi):
   ```bash
   DJANGO_ALLOWED_HOSTS="<your-LAN-IP>,localhost" python manage.py runserver 0.0.0.0:8000
   ```
2. Start the app: `cd mobile && npm install && npx expo start`

Then open **Expo Go** on the phone and scan the QR code. The login screen
pre-fills `http://<computer IP>:8000`.

## Checks

```bash
npm test           # scheduler + blitz order vs ../cards/scheduler_vectors.json
npm run typecheck
```

## Layout

- `src/app/` — screens (Expo Router). `(tabs)/` = Study, Library, Profile.
- `src/lib/scheduler.ts`, `blitz.ts` — ports of `cards/scheduler.py`, `cards/blitz.py`; keep in step.
- `src/lib/db.ts` — local schema and queries; `sync.ts` — push outbox / pull changes.
- `src/lib/i18n.ts` — all UI strings (ru, en).
