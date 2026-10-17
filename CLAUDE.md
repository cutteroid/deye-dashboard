# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Web dashboard for Deye solar inverters using the Solarman V5 protocol. Displays real-time solar production, battery status, grid power, home consumption, weather, and power outage schedules. Includes a Telegram bot for notifications in literary Ukrainian style.

## Development Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run dashboard (http://localhost:8080), served by waitress
python app.py
DASHBOARD_DEV=1 python app.py   # Flask debugger, no reloader (dev only)

# Tests (tests/ only, see pytest.ini; ~5s)
python -m pytest

# Run locally with Telegram disabled
./deploy_local.sh

# Deploy to remote server (interactive setup on first run)
./deploy.sh

# Test inverter connection
python test_connection.py

# Quick inverter health check
python check_inverter.py

# Diagnostic register scans
python scan_registers.py    # all registers
python scan_battery.py      # battery registers
python scan_phases.py       # phase registers
```

## Architecture

### Core Components

- **`app.py`** — Flask web server. Contains the main application, API routes, and background poller classes (`InverterPoller`, `WeatherPoller`). Serves the single-page dashboard at `/` and JSON API at `/api/*`. Manages phase stats and grid daily logs as JSON files.

- **`inverter.py`** — `DeyeInverter` class for Modbus communication via `pysolarmanv5`. Reads holding registers with 50ms delays between reads to avoid overwhelming the logger. `BatterySampler` runs in a separate thread to smooth voltage/SOC readings using a rolling buffer with outlier rejection. `InverterConfig` dataclass describes inverter capabilities (phases, battery, PV strings).

- **`telegram_bot.py`** — Telegram bot with commands (`/battery`, `/outage`, `/grid`, `/test`). Sends notifications for low battery and grid restore events. Messages are written in 1800s literary Ukrainian style. Uses `poems.py` for weather-themed poetry excerpts.

- **`templates/index.html`** — Single-page dashboard markup (cards, banners, settings panel, onboarding wizard). Passes server values to the JS via a small inline `window.DASHBOARD_CONFIG` (locales, default language, first-run flag).

- **`static/css/dashboard.css`** / **`static/js/dashboard.js`** — All styles and frontend logic (auto-refresh every 5 seconds, phase analytics, planned outages, fullscreen kiosk mode). Plain files, no build step; they must not contain Jinja syntax. Linked via `asset_url()`, which appends a content hash (`?v=…`) so browsers pick up changes after updates.

- **`locales/*.json`** — UI translations (`en` default, `uk`, `ru`), embedded into the page by `app.py`. Never hardcode user-facing text in `index.html` / `dashboard.js`: static markup uses `data-i18n="key"` / `data-i18n-attr="title:key"`, JS uses `t('key', {param})`, and text on elements that also carry a static key must go through `setI18nText()` / `setPlainText()` so language switches re-translate it. Add every new key to all locale files (`tests/test_i18n.py` enforces matching keys and placeholders).

### Outage Providers

`outage_providers/` is a provider pattern for power outage schedules:
- `base.py` — `OutageProvider` base class, `OutageSchedulePoller` (background thread), and `create_outage_provider()` factory
- `lvivoblenergo.py` — Lvivoblenergo schedule provider
- `yasno.py` — Yasno (DTEK) schedule provider
- `dtek.py` — DTEK regions (Kyiv oblast, Kyiv, Dnipro, Odesa) via the outage-data-ua community feed

Providers implement `fetch_days()` (today, plus tomorrow once published) and raise `OutageFetchError` on failure — an empty window list means "no outages", so never return `[]` for an error.

### Threading Model

Background services start once in `main()` (`init_services()`), not at import — importing `app` (tests, WSGI) starts nothing. Do not reintroduce a reloader/multi-process server: every poller would run in each process.

The app runs several daemon threads:
- `InverterPoller` — polls inverter every 60s, caches to JSON file
- `inverter-detect` — one-off background auto-detect; updates the shared `InverterConfig` in place and saves it to `inverter_config.json` for the next start
- `BatterySampler` — reads battery voltage/SOC every 30s for smoothing (idle when no battery)
- `WeatherPoller` — fetches Open-Meteo weather every 15 min
- `OutageSchedulePoller` — fetches outage schedule every 60s
- `TelegramBot` — runs Telegram polling loop

All pollers use thread locks for safe cache access. The inverter connection (`DeyeInverter.lock`) is shared between `InverterPoller`, `BatterySampler` and auto-detect. The Telegram bot reads `InverterPoller.data` (no direct inverter reads).

Data files (stats, logs, caches, bot state) go through `storage.py`: `atomic_write_json()` (temp file + fsync + rename, safe across power cuts) and `load_json()` (missing/corrupt file → default; corrupt files are moved to `*.corrupt`). Read-modify-write updates in `app.py` hold `_data_lock`.

Config saved from the UI is validated by `setup.validate_config()` (types, ranges, no line breaks, no unknown keys) before `.env` is written.

## Inverter Connection

- Uses `pysolarmanv5` library for Modbus over TCP
- Port 8899 (Solarman V5 protocol)
- **Use holding registers** (`read_holding_registers`), not input registers
- Slave ID: 1
- Connection is opened per-poll and closed after each read cycle (see `read_all_data` → `disconnect()` in finally block)
- 50ms sleep between register reads to reduce logger connection pressure
- Configuration via environment variables: `INVERTER_IP`, `LOGGER_SERIAL`
- Inverter capabilities (phases, battery, PV strings) auto-detected at startup via `detect_config()`

## Key Registers (Holding) — 3-Phase Hybrid

| Register | Description | Scale |
|----------|-------------|-------|
| 514, 515 | PV1/PV2 Power | W |
| 586 | Battery Current (signed) | /100 A |
| 587 | Battery Voltage | /100 V |
| 588 | Battery SOC | % |
| 598 | Grid Voltage | /10 V |
| 607 | Grid Power (signed) | W |
| 644-646 | Phase Voltages L1-L3 | /10 V |
| 650-653 | Phase Loads L1-L3, Total Load | W |
| 667 | Generator Power (GEN/GRID2 port) | W |
| 502, 520, 521, 526 | Daily PV/Import/Export/Load | /10 kWh |

## Key Registers (Holding) — 1-Phase Hybrid (Sunsynk)

| Register | Description | Scale |
|----------|-------------|-------|
| 186, 187 | PV1/PV2 Power | W |
| 191 | Battery Current (signed, negate) | /100 A |
| 183 | Battery Voltage | /100 V |
| 184 | Battery SOC | % |
| 150 | Grid Voltage | /10 V |
| 169 | Grid Power (signed) | W |
| 166 | Generator Power (GEN/GRID2 port) | W |
| 176, 178 | Load L1, Total Load | W |
| 108, 76, 77, 84 | Daily PV/Import/Export/Load | /10 kWh |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/data` | GET | Current inverter readings |
| `/api/weather` | GET | Current weather and forecast |
| `/api/outage_schedule` | GET | Outage status and today's/tomorrow's planned windows |
| `/api/phase-stats` | GET | Daily phase statistics |
| `/api/phase-history` | GET | Phase power history |
| `/api/generator` | GET | Generator status and runtime |
| `/api/phase-stats/clear` | POST | Clear phase statistics |

## Configuration

All via environment variables (`.env` file). See `.env.example` for full template.

Required: `INVERTER_IP`, `LOGGER_SERIAL`

Optional: `SETTINGS_PIN` (settings panel PIN, default `0000`; endpoints behind it use `@require_settings_pin`), `WEATHER_LATITUDE/LONGITUDE`, `OUTAGE_PROVIDER` (lvivoblenergo/yasno/dtek/none), `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`
