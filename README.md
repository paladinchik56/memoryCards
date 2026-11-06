# Cards 📇

A spaced-repetition flashcard app built with Django. Create cards, review them on a schedule that adapts to how well you know each one, organize them into shareable collections, and track progress against friends.

> **Status: work in progress.** The feature set below is functional and tested, but the visual design is still the rough first pass. The plan is to redesign the UI properly, then cut a proper release.

## Features

- **Spaced repetition** — each card moves along a fixed ladder of review intervals (90 seconds → 2 months); a correct answer advances it, a wrong one steps it back.
- **Flip-card review** — click the card (or answer it) to reveal the back, in a real 3D flip.
- **Collections** — group your cards into named collections with three visibility levels: private, unlisted (share by link), or public (listed in the shared library).
- **Shared library** — browse other users' public collections and copy ("take") individual cards into your own, starting fresh at stage 0.
- **Friends & progress** — add friends by nickname or email, see their current level based on how many cards they've mastered.
- **Nickname or email login** — register with a nickname (used for friends/sharing) and sign in with either it or your email.
- **Dark mode** — toggle in the top bar, remembered across visits.
- **Test mode** — a toggle that compresses review intervals to seconds, for trying out the whole scheduling flow without waiting.

## Screenshots

| | |
|---|---|
| ![Card list, light theme](docs/screenshots/cards-light.png) | ![Card list, dark theme](docs/screenshots/cards-dark.png) |
| ![Review — question side](docs/screenshots/review-question.png) | ![Review — answer side, after flipping](docs/screenshots/review-answer.png) |
| ![Friends and progress](docs/screenshots/friends.png) | ![Public library](docs/screenshots/library.png) |

## Tech stack

Django 6.1, SQLite, server-rendered templates with vanilla CSS/JS (no frontend framework, no build step).

## Getting started

```bash
git clone https://github.com/paladinchik56/memoryCards.git
cd memoryCards
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -r requirements.txt  # or: pip install django
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`, register an account (confirmation codes are sent via Django's console email backend by default — check your terminal output for the code), and start adding cards.

In production, set a `DJANGO_SECRET_KEY` environment variable (the repo only ships a `django-insecure-...` fallback for local dev).

Run the test suite with:

```bash
python manage.py test
```

## Mobile API

JSON API for the (upcoming) offline-first mobile app, under `/api/`. Every call except login sends `Authorization: Token <token>`.

| Method | Path | What |
|---|---|---|
| POST | `/api/auth/token/` | `{login, password}` (nickname or email) → `{token, user}` |
| POST | `/api/auth/logout/` | revoke the token |
| GET | `/api/me/` | current user |
| GET | `/api/scheduler/` | the review interval ladder |
| GET | `/api/library/` | public collections of other users |
| GET | `/api/shared/<share_token>/` | one collection with its cards |
| POST | `/api/shared/<share_token>/take/` | copy it: `{target: "new" \| null \| "<collection uuid>", cards?: [uuid]}` |
| POST | `/api/sync/` | push local changes + pull server changes since `since` |

Sync model (full contract in the `sync` docstring in `api/views.py`):
- Every card, collection and review has a client-generated UUID, so the app can create them offline.
- Progress is synced as **review events** (`card, correct, reviewed_at`), never as a stage number: the server replays them with the same scheduler as the website, idempotently by event UUID.
- Card text and collections: the later edit wins (`content_updated_at` / `updated_at`); reviews don't count as edits.
- Deletions travel as tombstones in `deleted`.
- `cards/scheduler_vectors.json` is the shared contract for the interval ladder; the app's tests must check against it.

## Roadmap

- [ ] Redesign the UI (current styling is functional, not polished)
- [ ] First tagged release
