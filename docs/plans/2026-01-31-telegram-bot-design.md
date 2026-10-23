# Telegram Bot for Battery & Grid Monitoring

> **Historical design note (January 2026), kept for background:** parts of it no longer match the code. The bot now reads the dashboard's inverter data instead of polling the inverter itself; it detects a grid outage from `grid_online` (the inverter's grid relay and every phase's voltage), not from `grid_voltage` below 50 V; the low-battery alert re-arms at 35%; and there are more commands (`/battery`, `/outage`, `/grid`). See `telegram_bot.py`.

## Overview

Telegram bot integrated into the Deye dashboard server that monitors battery SOC and grid status, sending notifications in 1800s literary Ukrainian style.

## Configuration

Environment variables:
- `TELEGRAM_BOT_TOKEN` — bot token from BotFather
- `TELEGRAM_ALLOWED_USERS` — comma-separated numeric user IDs

## Architecture

- `telegram_bot.py` — `TelegramBot` class with monitoring loop, message sending, command handling
- Background thread in `app.py` polling every 2 minutes
- Uses raw `requests` library to call Telegram HTTP API (no bot framework)

## Monitoring Logic

### Battery (SOC < 30%)
- Notify once when SOC drops below 30%
- Reset when SOC goes back above 30%
- No repeat notifications while low

### Grid Restore (voltage debounce)
- Grid "down" when `grid_voltage` < 50V
- Grid "restored" when voltage returns above 50V
- 1-minute debounce: state must be consistent across two consecutive polls (2-min interval)
- Only notify on grid restore, not on grid loss

## Bot Commands

- `/start` — replies with user's numeric Telegram ID
- `/test` — sends both sample messages (battery low + grid restored)

## Message Style

1800s literary Ukrainian (Kotlyarevsky/Shevchenko era), humorous.

## Deployment

- Add `telegram_bot.py` to `deploy.sh` FILES array
- Add `requests` to `requirements.txt`
- Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USERS` to remote `.env`
