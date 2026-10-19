# Extended Dashboard

A web dashboard for monitoring Deye solar inverters in real-time. Supports both single-phase (e.g. SUN-6K-SG03LP1) and 3-phase hybrid models. Displays solar production, battery status, grid power, home consumption, weather conditions, and power outage schedules.

![Dashboard Preview](docs/preview.png)

## How It Works (for non-technical users)

This project is a **home energy dashboard** — a web page that shows you what your solar panels are producing, how much battery you have left, whether you're using grid power, and when the next power outage is scheduled.

### What you need

1. **A Deye solar inverter** with a Solarman Wi-Fi logger stick (the small antenna plugged into your inverter). Most Deye hybrid inverters come with one.

2. **A small home computer** that runs 24/7 on your local network. The best option is a **Raspberry Pi Zero 2W** (~$15) or any Raspberry Pi model. It uses very little power and sits quietly on your network. Any Linux computer (old laptop, mini PC, etc.) works too.

3. **Your home Wi-Fi network** — both the inverter's logger stick and the Raspberry Pi must be connected to the same network.

### How it works

```
Solar Panels → Deye Inverter → Wi-Fi Logger Stick
                                       ↓
                              Your Home Network
                                       ↓
                              Raspberry Pi (runs this dashboard)
                                       ↓
                              Your Phone / Tablet / PC (opens the dashboard in a browser)
```

The Raspberry Pi reads data from your inverter every 60 seconds over your local network. It then shows this data on a web page you can open from any device in your home — phone, tablet, or computer — by going to the Raspberry Pi's address in a browser (e.g. `http://192.168.1.50:8080`).

### Setup overview

1. **Get a Raspberry Pi** and install Raspberry Pi OS on it (many YouTube tutorials available)
2. **Connect it to your Wi-Fi** and make sure it has a fixed IP address
3. **Run the deploy script** from your computer — it copies everything to the Pi and starts the dashboard automatically
4. **Open the dashboard** in your browser — on first launch, a setup wizard will guide you through connecting to your inverter

You don't need to be a programmer, but you should be comfortable with basic computer tasks like connecting to Wi-Fi and following step-by-step instructions. If you have a tech-savvy friend or family member, ask them to help with the initial setup — after that, the dashboard runs on its own.

---

## Як це працює (для нетехнічних користувачів)

Цей проект — це **домашня енергетична панель** — веб-сторінка, яка показує, скільки електроенергії виробляють ваші сонячні панелі, який заряд акумулятора, чи використовуєте ви електрику з мережі, та коли заплановане наступне відключення.

### Що вам потрібно

1. **Сонячний інвертор Deye** з Wi-Fi логером Solarman (маленька антена, підключена до інвертора). Більшість гібридних інверторів Deye комплектуються таким.

2. **Невеликий домашній комп'ютер**, який працює постійно у вашій локальній мережі. Найкращий варіант — **Raspberry Pi Zero 2W** (~$15) або будь-яка модель Raspberry Pi. Він споживає дуже мало енергії та тихо працює у вашій мережі. Будь-який Linux-комп'ютер (старий ноутбук, міні-ПК тощо) також підійде.

3. **Ваша домашня Wi-Fi мережа** — і логер інвертора, і Raspberry Pi мають бути підключені до однієї мережі.

### Як це працює

```
Сонячні панелі → Інвертор Deye → Wi-Fi логер
                                       ↓
                              Ваша домашня мережа
                                       ↓
                              Raspberry Pi (запускає цю панель)
                                       ↓
                              Ваш телефон / планшет / ПК (відкриває панель у браузері)
```

Raspberry Pi зчитує дані з вашого інвертора кожні 60 секунд через локальну мережу. Потім він відображає ці дані на веб-сторінці, яку можна відкрити з будь-якого пристрою у вашому домі — телефону, планшета чи комп'ютера — перейшовши за адресою Raspberry Pi у браузері (наприклад, `http://192.168.1.50:8080`).

### Огляд налаштування

1. **Придбайте Raspberry Pi** та встановіть на нього Raspberry Pi OS (багато відеоінструкцій на YouTube)
2. **Підключіть його до Wi-Fi** та переконайтесь, що він має фіксовану IP-адресу
3. **Запустіть скрипт розгортання** з вашого комп'ютера — він скопіює все на Pi та автоматично запустить панель
4. **Відкрийте панель** у браузері — при першому запуску майстер налаштування допоможе вам підключитися до інвертора

Вам не потрібно бути програмістом, але ви повинні вміти виконувати базові завдання на комп'ютері, такі як підключення до Wi-Fi та слідування покроковим інструкціям. Якщо у вас є технічно обізнаний друг чи родич, попросіть їх допомогти з початковим налаштуванням — після цього панель працює самостійно.

---

## Features

- **Real-time monitoring** — solar production, battery SOC, grid power, and load consumption
- **Load analytics** — per-phase power distribution with daily statistics (3-phase systems)
- **Weather** — current conditions and forecast via Open-Meteo API
- **Planned outages** — today's and tomorrow's outage windows on a timeline, plus a countdown in the grid banner (Lvivoblenergo, Yasno, or DTEK providers)
- **Air raid alerts** — map of Ukraine's regions and districts with live alert statuses (NEPTUN)
- **Smart meter** — power, voltage, current and energy from a Bakler Wi-Fi electricity meter over MQTT (optional)
- **Grid outage detection** — browser notifications when power goes out
- **Telegram bot** — battery reports, inverter status, and Ukrainian weather poems
- **Fullscreen mode** — kiosk-friendly display with weather, grid, and battery banners
- **Responsive design** — works on desktop and mobile

## Requirements

- Python 3.7+
- Deye inverter with Solarman Wi-Fi logger
- Network access to the inverter

## Quick Start

```bash
git clone https://github.com/ivanursul/deye-dashboard.git
cd deye-dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file from the example and fill in your values:

```bash
cp .env.example .env
# Edit .env with your inverter IP, logger serial, etc.
```

Run the dashboard:

```bash
python app.py
```

Open http://localhost:8080 in your browser. The app is served by [waitress](https://docs.pylonsproject.org/projects/waitress/) (a production WSGI server). For local development with the Flask debugger, run `DASHBOARD_DEV=1 python app.py` — never on a device reachable from the network.

Inverter capabilities (phases, battery, PV strings, generator) are auto-detected in the background after startup. The inverter's device type (register 0) tells its family: Deye single-phase hybrid, three-phase low-voltage hybrid and three-phase high-voltage hybrid inverters are supported (HV models scale some values differently, handled automatically); string and micro inverters use other register maps and get a warning on the dashboard. Detection results are saved to `inverter_config.json` (override the path with `INVERTER_CONFIG_FILE`); the next start uses the saved result immediately. Set `INVERTER_PHASES`, `INVERTER_HAS_BATTERY`, `INVERTER_PV_STRINGS` and `INVERTER_HAS_GENERATOR` to skip detection.

Run the tests:

```bash
pip install pytest
python -m pytest        # runs tests/ (see pytest.ini), takes a few seconds
```

## Docker

You can also run the dashboard using Docker, which is the recommended approach for production deployments.

### Using Docker Compose (Recommended)

```bash
# Create and configure .env file
cp .env.example .env
# Edit .env with your inverter IP, logger serial, etc.

# Build and start the dashboard
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the dashboard
docker-compose down
```

### Using Docker CLI

```bash
# Build the image
docker build -t deye-dashboard:latest .

# Run the container
docker run -d \
  --name deye-dashboard \
  -p 8080:8080 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  deye-dashboard:latest
```

### Running on Another Machine Without Building (e.g. Synology NAS)

`tools/export_images.sh` packs the dashboard and Mosquitto images with a ready-to-run `docker-compose.yml` into `dist/extended-dashboard-<arch>.tar.gz`; the target machine needs only Docker, no source code or build. Pass the target CPU: `arm64` (default on Apple Silicon; Raspberry Pi 4/5, Synology j/value models such as DS223j) or `amd64` (Intel/AMD PCs, Synology "+" models). Install steps for Synology and plain Linux are in `INSTALL.md` inside the archive. Your `data/.env` is not included (it holds secrets) — copy it over yourself if you want the same settings.

```bash
tools/export_images.sh          # this machine's architecture
tools/export_images.sh amd64    # cross-build for an Intel/AMD machine
```

**Updates:** `tools/deploy_nas.sh` sends only the files the image is built from (~0.2 MB) to the NAS over SSH and rebuilds there (`docker compose up -d --build`); Docker reuses its cached layers, so a code-only update takes seconds. The first run asks for the SSH login and the dashboard folder on the NAS (saved to `tools/.deploy_nas.env`, not committed) and is slow once, because the NAS downloads the Python base image and installs the packages. `data/` on the NAS is never touched. `sudo` asks for the NAS password on each run; set up an SSH key (`ssh-copy-id user@nas`) to skip the login prompt. `tools/deploy_nas.sh --setup` changes the saved address.

### Data Persistence

The container mounts a `data` volume at `/app/data` for persistent storage of:
- Configuration (`.env`)
- Phase statistics (`phase_stats.json`)
- Phase history (`phase_history.json`)
- Smart meter daily counter (`smart_meter_daily.json`) and Mosquitto broker files (`mosquitto/`)

### Health Checks

The container includes a built-in health check that pings the `/api/data` endpoint every 30 seconds. Check the health status with:

```bash
docker ps  # Shows health status
docker inspect deye-dashboard --format='{{.State.Health.Status}}'
```

For detailed Docker configuration options, troubleshooting, and production deployment tips, see [DOCKER.md](DOCKER.md).

## Configuration

All configuration is done via environment variables, typically set in a `.env` file. See `.env.example` for a complete template.

### Inverter (required)

| Variable | Description | Example |
|----------|-------------|---------|
| `INVERTER_IP` | IP address of your Deye inverter on the local network | `192.168.1.100` |
| `LOGGER_SERIAL` | Serial number of the Solarman Wi-Fi logger (printed on the stick or found in the Solarman app) | `1234567890` |

### Inverter Capabilities (optional)

These are auto-detected at startup. Set them only if auto-detection doesn't work for your model.

| Variable | Description | Default |
|----------|-------------|---------|
| `INVERTER_PHASES` | Number of phases (`1` or `3`); also in Settings → Edit configuration (step 1) | auto-detected |
| `INVERTER_HAS_BATTERY` | Whether a battery is connected (`true` / `false`) | auto-detected |
| `INVERTER_PV_STRINGS` | Number of PV strings (`1` or `2`) | auto-detected |

### Weather

| Variable | Description | Default |
|----------|-------------|---------|
| `WEATHER_LATITUDE` | Latitude for weather forecast | `50.4501` |
| `WEATHER_LONGITUDE` | Longitude for weather forecast | `30.5234` |

Coordinates are used to fetch weather data from the [Open-Meteo API](https://open-meteo.com/). Find your coordinates on [latlong.net](https://www.latlong.net/).

### Outage Schedule

| Variable | Description | Default |
|----------|-------------|---------|
| `OUTAGE_PROVIDER` | Provider name: `lvivoblenergo`, `yasno`, `dtek`, or `none` | `none` |
| `OUTAGE_GROUP` | Your outage queue/group number (e.g. `1.1`, `2.2`) | — |

**Yasno-specific settings** (only when `OUTAGE_PROVIDER=yasno`):

| Variable | Description | Default |
|----------|-------------|---------|
| `OUTAGE_REGION_ID` | Yasno region ID (e.g. `25` for Kyiv) | — |
| `OUTAGE_DSO_ID` | Yasno DSO ID (e.g. `902` for DTEK Kyiv) | — |

**DTEK-specific settings** (only when `OUTAGE_PROVIDER=dtek`):

DTEK has no public API, so this provider reads the community feed [outage-data-ua](https://github.com/Baskerville42/outage-data-ua), which mirrors DTEK's published schedules every few minutes. Only definite outages are shown; "possible outage" hours are ignored.

| Variable | Description | Default |
|----------|-------------|---------|
| `OUTAGE_DTEK_REGION` | `kyiv-region` (Kyiv oblast), `kyiv`, `dnipro`, or `odesa` | `kyiv-region` |

### Settings PIN

The settings panel (gear button) opens without a PIN for local, per-device settings such as low power mode (the language button is also always available). Server-side settings — OTA update/rollback, Edit Configuration and Factory Reset — are locked behind the settings PIN (**Unlock** in the panel) and lock again when the panel closes. The server enforces the same PIN on the API endpoints behind them: config read/save/reset, inverter discovery, OTA check/update/rollback and clearing phase statistics. After 5 wrong attempts, PIN checks are locked for 60 seconds.

| Variable | Description | Default |
|----------|-------------|---------|
| `SETTINGS_PIN` | PIN for the settings panel | `0000` |

This is basic protection for a kiosk display, not real authentication: the PIN is sent in plain HTTP. Factory Reset deletes `.env`, which resets the PIN to `0000`. During first-run setup no PIN is required.

### Air Raid Alerts

The **Air raid alerts** card shows a map of Ukraine's regions and districts (raions) coloured by status: red — air raid alert, yellow — threat (yellow level, e.g. drones). Alerts can cover a whole region or single districts. In fullscreen mode the map sits next to Planned outages on the first screen.

Data comes from [NEPTUN](https://neptun.in.ua/) ([developer docs](https://neptun.in.ua/developers)): free REST API, no key needed. The server requests `GET https://neptun.in.ua/api/v1/alerts` every 30 seconds (their terms allow at most one request per 5 seconds) with `If-None-Match`, so unchanged data isn't re-downloaded. As required by NEPTUN's [terms of use](https://neptun.in.ua/api-terms), the card shows a visible "Source: NEPTUN" link and a note that it is not an official alert system.

| Variable | Description | Default |
|----------|-------------|---------|
| `AIR_ALERTS_PROVIDER` | `neptun`, `mock` (demo data, marked "Demo data") or `none` to hide the card | `neptun` |

**Map data:** `static/data/ukraine-regions.json` is generated by `tools/build_ukraine_map.py` from the OCHA Common Operational Dataset *Ukraine – Subnational Administrative Boundaries* (State Scientific Production Enterprise "Kartographia"), licensed [CC BY-IGO](https://creativecommons.org/licenses/by/3.0/igo/), source: [data.humdata.org/dataset/cod-ab-ukr](https://data.humdata.org/dataset/cod-ab-ukr). NEPTUN alerts are matched to it by Ukrainian region/district name (with aliases for raions NEPTUN still lists under their pre-2024 names).

### Smart Meter (optional)

The **Smart meter** card shows live readings from a [Bakler](https://www.bakler.com.ua/) Wi-Fi electricity meter: current power, voltage and current (a per-phase table for three-phase meters, where a phase below 100 V is shown as "No voltage"), mains frequency and the relay state. When the meter or the broker is unavailable, a badge says so (Waiting for data / Meter offline / No recent data / MQTT broker unavailable) and the last known readings are dimmed. The relay is shown only; the dashboard never switches it.

The meter talks MQTT: it connects to a broker and publishes its readings there ([MQTT docs, in Ukrainian](https://www.bakler.com.ua/setting-mqtt-client/)). `docker compose` starts a Mosquitto broker (`deye-mosquitto`, port 1883) next to the dashboard.

1. Add to `data/.env` (choose your own user name and password):
   ```
   SMART_METER_ENABLED=true
   SMART_METER_MQTT_USER=meter
   SMART_METER_MQTT_PASSWORD=choose-a-long-password
   ```
2. `docker compose up -d` (restarts the broker and the dashboard with the new settings).
3. In the meter's app open **Settings → Integration → MQTT** and enter: broker = IP address of the dashboard machine on your network, port `1883`, the same user name and password.

The card appears with "Waiting for data" and fills in after the meter's first message. The dashboard asks the meter to send readings every `SMART_METER_INTERVAL` seconds; the full summary (frequency, relay) arrives once a minute.

Without `SMART_METER_MQTT_USER` / `SMART_METER_MQTT_PASSWORD` the broker accepts no connections from the network, so it is never open without a password.

| Variable | Description | Default |
|----------|-------------|---------|
| `SMART_METER_ENABLED` | Show the card and connect to the broker | `false` |
| `SMART_METER_MQTT_USER` / `SMART_METER_MQTT_PASSWORD` | Broker login (also creates the Mosquitto user) | — |
| `SMART_METER_MQTT_HOST` | Use another broker instead of the bundled one | `mosquitto` in Docker, else `localhost` |
| `SMART_METER_MQTT_PORT` | Broker port | `1883` |
| `SMART_METER_SERIAL` | Meter serial (topic `buckler/<serial>/…`) when several meters share the broker; otherwise the first one seen is used | — |
| `SMART_METER_INTERVAL` | Update interval requested from the meter, 1–60 s (`0` = leave the meter's setting) | `10` |
| `SMART_METER_DAILY_FILE` | Where today's starting counter is kept | `data/smart_meter_daily.json` |
| `SMART_METER_DEMO` | `1` / `3`: show simulated single-/three-phase readings (marked "Demo data") instead of a real meter; no broker needed. The three-phase demo drops L3 for the first minute of every 5 minutes | — |

### Language

The dashboard UI is available in English (default), Ukrainian and Russian. Switch with the language button next to the fullscreen button, which opens a list of the available languages; the choice is stored in the browser's local storage, so each device keeps its own language.

Translations live in `locales/<lang>.json` (one file per language, nested keys, `{name}` placeholders). To add a language, copy `locales/en.json` to e.g. `locales/pl.json`, translate the values, and restart — the language button picks it up automatically. `tests/test_i18n.py` checks that every locale has the same keys and placeholders as English.

The Telegram bot is Ukrainian-only and is not affected by this setting.

### Low Power Mode

For always-on wall tablets, **Settings → Display → Low power mode** turns off all animations, transitions and blur effects to reduce CPU/GPU load. It is stored per device (browser local storage). Animations are also turned off automatically when the device has the system "Reduce motion" accessibility setting enabled.

### Telegram Bot (optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_ENABLED` | Enable the Telegram bot (`true` / `false`) | `false` |
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) | — |
| `TELEGRAM_ALLOWED_USERS` | Comma-separated list of allowed Telegram user IDs | — |

**How to set up:**

1. Message [@BotFather](https://t.me/BotFather) on Telegram and create a new bot with `/newbot`
2. Copy the bot token into `TELEGRAM_BOT_TOKEN`
3. Find your Telegram user ID (see below), add it to `TELEGRAM_ALLOWED_USERS`
4. Set `TELEGRAM_ENABLED=true` and restart the dashboard

**How to find your Telegram user ID:**

There are two ways:

- **Using this bot** — set `TELEGRAM_ENABLED=true` with your bot token and leave `TELEGRAM_ALLOWED_USERS` empty for now. Start the dashboard, then open your bot in Telegram and send `/start`. The bot will reply with your numeric user ID (e.g. `123456789`). Add it to `TELEGRAM_ALLOWED_USERS` and restart.
- **Using @userinfobot** — search for `@userinfobot` in Telegram, start it, and it will immediately reply with your user ID.

For multiple users, separate IDs with commas: `TELEGRAM_ALLOWED_USERS=123456789,987654321`

**Bot commands:**

| Command | Description |
|---------|-------------|
| `/start` | Shows your Telegram user ID and authorization status |
| `/battery` | Current battery SOC, voltage, power, and estimated time remaining |
| `/outage` | Next scheduled power outage window and countdown |
| `/grid` | Daily grid consumption report (import/export) |
| `/test` | Sends sample battery and grid messages |

The bot also provides a keyboard with Ukrainian-labeled buttons for quick access. Messages include weather-themed Ukrainian poetry excerpts.

### Data Files (optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `PHASE_STATS_FILE` | Path to phase statistics JSON file | `phase_stats.json` |
| `PHASE_HISTORY_FILE` | Path to phase history JSON file | `phase_history.json` |

### Deployment (used by `deploy.sh`)

| Variable | Description | Example |
|----------|-------------|---------|
| `DEPLOY_HOST` | Remote server IP or hostname | `192.168.1.50` |
| `DEPLOY_USER` | SSH user on the remote server | `pi` |
| `DEPLOY_DIR` | Installation directory on the remote server | `/home/pi/deye-dashboard` |
| `DEPLOY_SERVICE_NAME` | Systemd service name | `deye-dashboard` |

## Local Development

Use `deploy_local.sh` to run the dashboard locally with the Telegram bot disabled:

```bash
chmod +x deploy_local.sh
./deploy_local.sh
```

This sources your `.env`, overrides `TELEGRAM_ENABLED=false`, activates the virtual environment, and starts the app. Useful for UI development without triggering bot messages.

You need a `.env` file with at least `INVERTER_IP` and `LOGGER_SERIAL` set. Either create one manually from `.env.example` or run `./deploy.sh` once to generate it interactively.

## Deploying to a Remote Server

`deploy.sh` deploys the dashboard to a remote Linux server over SSH and sets it up as a systemd service. The remote server needs Python 3.7+, SSH access, and `sudo` for systemd management.

### Prerequisites

- SSH key-based access to the remote server (the script runs `ssh` and `rsync` non-interactively)
- `sudo` privileges on the remote server (for systemd service setup)
- Python 3.7+ installed on the remote server

### First-time deploy

If no `.env` file exists, the script runs an interactive setup wizard:

```bash
chmod +x deploy.sh
./deploy.sh
```

The wizard prompts for all settings in order:

1. **Inverter** — IP address and logger serial number
2. **Deployment** — remote host, SSH user, install directory, service name
3. **Weather** — latitude and longitude for forecast (defaults to Kyiv)
4. **Outage schedule** — provider selection (Lvivoblenergo, Yasno, or none) with provider-specific follow-up questions
5. **Telegram** — enable/disable, bot token, and allowed user IDs

After answering all prompts, the script:
- Writes the `.env` file
- Prints a summary of all settings
- Asks for confirmation before deploying

If you decline, the `.env` is kept so you can edit it and re-run `./deploy.sh`.

### Subsequent deploys

When `.env` already exists, the script skips all prompts and deploys immediately:

```bash
./deploy.sh
```

To change settings, edit `.env` directly and re-deploy.

### What the deploy script does

1. **Rsync** — copies `app.py`, `inverter.py`, `telegram_bot.py`, `poems.py`, `outage_providers/`, `requirements.txt`, `templates/`, and `.env` to the remote server
2. **Python setup** — creates a virtual environment (if needed) and installs dependencies from `requirements.txt`
3. **Systemd service** — creates a service file at `/etc/systemd/system/<service-name>.service`, enables it, and restarts it
4. The dashboard runs on port 8080 by default

### Managing the remote service

```bash
# Check status
ssh user@host 'sudo systemctl status deye-dashboard'

# View live logs
ssh user@host 'sudo journalctl -u deye-dashboard -f'

# Restart after config changes
ssh user@host 'sudo systemctl restart deye-dashboard'

# Stop the service
ssh user@host 'sudo systemctl stop deye-dashboard'
```

## Finding Your Inverter Details

### Inverter IP

Check your router's connected devices list or scan your network:

```bash
nmap -sP 192.168.1.0/24
```

### Logger Serial Number

The serial number is printed on the Solarman Wi-Fi logger stick, or can be found in the Solarman app under device settings.

## Utility Scripts

```bash
# Test inverter connection
python test_connection.py

# Scan for battery voltage register
python scan_battery.py

# Scan for phase-related registers
python scan_phases.py

# Scan all available registers
python scan_registers.py
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/data` | GET | Current inverter readings |
| `/api/weather` | GET | Current weather and forecast |
| `/api/outage_schedule` | GET | Current outage status, plus today's and (if published) tomorrow's planned windows |
| `/api/phase-stats` | GET | Daily phase statistics |
| `/api/phase-history` | GET | Phase power history |
| `/api/phase-stats/clear` | POST | Clear phase statistics |

## License

MIT License
