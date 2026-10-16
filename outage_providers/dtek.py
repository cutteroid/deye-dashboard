"""Outage schedule provider for DTEK regions (Kyiv oblast, Kyiv, Dnipro, Odesa).

DTEK's own sites (e.g. dtek-krem.com.ua) have no public API and sit behind an
anti-bot WAF, so this reads the community mirror outage-data-ua, which scrapes
them every few minutes and republishes DTEK's schedule object as JSON:
https://github.com/Baskerville42/outage-data-ua
"""
import os
import logging
from datetime import datetime, date, timedelta

import requests

from outage_providers.base import OutageProvider, OutageFetchError

logger = logging.getLogger(__name__)

DATA_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/data/{region}.json"
)
DEFAULT_REGION = "kyiv-region"
REGIONS = {
    "kyiv-region": "ДТЕК Київські регіональні електромережі",
    "kyiv": "ДТЕК Київські електромережі",
    "dnipro": "ДТЕК Дніпровські електромережі",
    "odesa": "ДТЕК Одеські електромережі",
}

# Hourly slot values from DTEK's schedule, mapped to which half-hours are off.
# "maybe"/"mfirst"/"msecond" are only possible outages and are treated as power on.
_OFF_HALVES = {
    "no": (True, True),
    "first": (True, False),
    "second": (False, True),
}


def slots_to_windows(slots):
    """Convert DTEK hourly slots {"1": "yes", ..., "24": "no"} to outage windows.

    Slot N covers the hour from N-1:00 to N:00. Returns a list of
    (start_hour, start_min, end_hour, end_min) with adjacent slots merged;
    an outage running to midnight ends at (24, 0).
    """
    halves = []
    for hour in range(1, 25):
        halves.extend(_OFF_HALVES.get(slots.get(str(hour)), (False, False)))

    windows = []
    start = None
    for i, off in enumerate(halves + [False]):
        if off and start is None:
            start = i
        elif not off and start is not None:
            sh, sm = divmod(start * 30, 60)
            eh, em = divmod(i * 30, 60)
            windows.append((sh, sm, eh, em))
            start = None
    return windows


class DtekProvider(OutageProvider):
    """Outage schedule provider for DTEK regions via the outage-data-ua feed."""

    def __init__(self, group=None, region=None):
        self.group = group or os.environ.get("OUTAGE_GROUP", "1.1")
        self.region = region or DEFAULT_REGION
        self.display_name = REGIONS.get(self.region, "ДТЕК")
        self.url = DATA_URL_TEMPLATE.format(region=self.region)

    @property
    def group_key(self):
        return self.group if self.group.startswith("GPV") else f"GPV{self.group}"

    def fetch_windows(self):
        """Fetch today's outage windows for the configured group."""
        return self.fetch_days()[date.today()]

    def fetch_days(self):
        """Fetch outage windows for today and, once DTEK publishes it, tomorrow."""
        if self.region not in REGIONS:
            # Reported as a fetch error rather than raised at startup, so a
            # bad config shows "schedule unavailable" instead of a crash loop.
            raise OutageFetchError(
                f"Unknown DTEK region '{self.region}' (expected one of: {', '.join(REGIONS)})"
            )
        logger.info("DTEK: fetching %s (group=%s)", self.url, self.group)
        try:
            resp = requests.get(self.url, timeout=15)
        except requests.RequestException as e:
            raise OutageFetchError(f"DTEK feed request failed: {e}") from e
        if not resp.ok:
            raise OutageFetchError(f"DTEK feed returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as e:
            raise OutageFetchError("DTEK feed returned invalid JSON") from e

        status = data.get("lastUpdateStatus") or {}
        if not status.get("ok", True):
            # The feed keeps the last good schedule on scrape errors; the
            # today-check below rejects it once it is no longer current.
            logger.warning("DTEK: feed scraper reports %s (code %s) at %s",
                           status.get("status"), status.get("code"), status.get("at"))

        fact = data.get("fact") or {}
        by_date = {}
        for ts, groups in (fact.get("data") or {}).items():
            try:
                by_date[datetime.fromtimestamp(int(ts)).date()] = groups
            except (TypeError, ValueError):
                continue

        today = date.today()
        if today not in by_date:
            raise OutageFetchError(
                f"DTEK: no schedule for {today} in feed (source updated {fact.get('update')})"
            )
        today_slots = by_date[today].get(self.group_key)
        if today_slots is None:
            names = sorted((g.removeprefix("GPV") for g in by_date[today]),
                           key=lambda g: [int(p) for p in g.split(".") if p.isdigit()])
            shown = ", ".join(names[:12]) + (", …" if len(names) > 12 else "")
            raise OutageFetchError(
                f"DTEK: group '{self.group}' not in {self.region} schedule "
                f"(available: {shown})"
            )

        result = {today: slots_to_windows(today_slots)}
        tomorrow = today + timedelta(days=1)
        tomorrow_slots = by_date.get(tomorrow, {}).get(self.group_key)
        if tomorrow_slots is not None:
            result[tomorrow] = slots_to_windows(tomorrow_slots)

        logger.info("DTEK: group %s today %s, tomorrow %s (source updated %s)",
                    self.group, result[today], result.get(tomorrow, "not published"),
                    fact.get("update"))
        return result
