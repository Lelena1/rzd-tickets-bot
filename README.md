# 🚆 RZD Tickets Bot

**English** | [Русский](README.ru.md)

A Telegram bot that searches Russian Railways (RZD) train tickets and
watches a specific train/car class for you, notifying you the moment
seats open up — including a dedicated filter for pet-friendly seats.

**Stack:** Python · [aiogram 3](https://docs.aiogram.dev/) · Playwright ·
SQLite · APScheduler

## What it does

- **`/search`** — pick a departure city, destination, and date through a
  step-by-step dialog with live autocomplete; get back every train on
  that route with seat counts, prices, and upper/lower berth breakdown
  per car class.
- **Seat tracking** — tap a car class under any train to watch it. The
  bot polls RZD in the background and messages you the moment the seat
  count goes up (e.g. a cancellation frees up a berth on a sold-out
  train). Tracking works per class — just "Купе", just "Плацкарт" — not
  only "any seat on this train."
- **🐾 Pet-friendly seats** — RZD marks certain car-class allocations as
  reserved for passengers travelling with small pets. The bot surfaces
  these as their own trackable option, separate from the regular
  allocation of the same class.
- **`/mytracking`** — see and cancel active watches.
- **Direct buy link** — every search result links straight to the
  matching page on `ticket.rzd.ru` so you finish the actual purchase on
  RZD's own site (the bot only searches and tracks; it never handles
  payment or passenger data).
- **Access control** — an optional allowlist of Telegram user IDs, so a
  bot you run for your own family isn't open to the whole internet.

## The interesting part: getting data out of ticket.rzd.ru

RZD doesn't publish a public API, and the site is actively defended
against scraping — which made this less of a "call a REST endpoint"
project and more of a small reverse-engineering exercise:

1. **Plain HTTP clients get silently blocked.** `httpx`/`requests`
   requests to `ticket.rzd.ru` return `200 OK` with an *empty body* —
   no error, just nothing. The cause turned out to be
   [BotFaqtor](https://botfaqtor.ru/), a commercial anti-bot service
   loaded on the page (`cdn.botfaqtor.ru/one.js`) that fingerprints the
   client and quietly drops requests that don't look like a real
   browser.
2. **A real (headless) browser gets through.** Driving actual Chromium
   via Playwright — even headless — passes BotFaqtor's checks, because
   it *is* a real browser engine. All requests are made through
   `fetch()` executed **inside** a page already on `ticket.rzd.ru`,
   rather than Playwright's separate `APIRequestContext` — the two use
   different network stacks, and `APIRequestContext` turned out to be
   unreliable (DNS resolution failures) on at least one test machine
   where in-page `fetch()` worked fine.
3. **Finding the real data source.** The first working version scraped
   the rendered search-results page's DOM. Watching the Network tab
   during a manual search turned up the actual backend endpoint the
   page itself calls —
   `/api/v1/railway-service/prices/train-pricing` — a single JSON
   response with far more detail than the UI shows (per-class upper/
   lower berth counts, a `HasPlacesNearPets` flag per car group, exact
   pricing). Switching to it cut a search from ~15–20s of
   DOM-rendering wait down to a couple of seconds, and made car-class
   tracking (including the pet-seat filter) possible at all — none of
   that granularity survives into the rendered page.
4. **Certificates.** `ticket.rzd.ru`'s certificate chains to a Russian
   government CA that isn't in most default trust stores, so every
   HTTP client in this project runs with certificate verification
   explicitly relaxed for that one host.

None of this is documented anywhere — the integration in
[`bot/rzd_api.py`](bot/rzd_api.py) is built entirely from observed
network traffic, and will need updating if RZD changes the site.

## Project structure

```
bot/
  rzd_api.py       — Playwright client for ticket.rzd.ru (stations, train search)
  db.py            — SQLite storage for active watches
  scheduler.py     — background job that re-checks watched trains
  middlewares.py   — Telegram user allowlist
  formatting.py    — train/seat message formatting
  keyboards.py     — inline keyboards (class picker, buy link, stop watch)
  states.py        — aiogram FSM states for /search
  utils.py         — date parsing/formatting
  config.py        — environment variables
  handlers/
    common.py      — /start, /help, /cancel
    search.py       — the /search dialog
    tracking.py     — watch setup, /mytracking
  main.py          — entry point (starts the browser, bot, and scheduler)
```

## Setup

```bash
git clone https://github.com/Lelena1/rzd-tickets-bot
cd rzd-tickets-bot
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env   # fill in a bot token from @BotFather
```

## Run

```bash
python -m bot.main
```

### Auto-start on Windows login

[`start_bot.bat`](start_bot.bat) wraps the run command with logging to
`bot_autostart.log`. To have it start automatically, drop a shortcut to
it into your Startup folder (`Win+R` → `shell:startup`) — this uses
Explorer's normal startup-shell mechanism. (A Task Scheduler "run at
logon" entry is the more common approach and usually works fine; on one
development machine it silently failed to spawn the process at all —
Task Scheduler reported success but the Windows Task Scheduler
operational log showed no process-creation event — so the Startup
folder was used instead as a more reliable fallback.)

## Known limitations

- **Not instant.** Each search is a real page load / API round-trip
  through a browser (a couple of seconds), not a cached lookup — fine
  for personal use, not built for high request volume.
- **Coupled to RZD's current site.** Field names and the one CSS
  selector still in use are snapshots of `ticket.rzd.ru` as it is
  today; a site redesign will require updating `bot/rzd_api.py`.
- **No bypass guarantee.** Headless-but-real-browser traffic passes
  BotFaqtor's checks today, but anti-bot services evolve; this isn't a
  permanent workaround.
- FSM state lives in memory (aiogram's `MemoryStorage`) — an in-progress
  `/search` dialog doesn't survive a restart, but saved watches (SQLite)
  do.
- A watch fires on an *increase* in seat count since the last check
  (including 0 → N), not on every poll where seats exist — so it
  doesn't repeat the same notification every 5 minutes.
