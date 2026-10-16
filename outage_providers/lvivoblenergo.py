"""Outage schedule provider for Lvivoblenergo (LOE)."""
import os
import re
import logging
from datetime import date, timedelta
from html.parser import HTMLParser

import requests

from outage_providers.base import OutageProvider, OutageFetchError

logger = logging.getLogger(__name__)

SCHEDULE_API_URL = "https://api.loe.lviv.ua/api/menus?page=1&type=photo-grafic"
DEFAULT_GROUP = "4.1"


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines = []
        self._current = []

    def handle_data(self, data):
        self._current.append(data)

    def handle_endtag(self, tag):
        if tag == "p" and self._current:
            self.lines.append("".join(self._current).strip())
            self._current = []


def parse_group_windows(html, group):
    """Parse outage time windows for a specific group from rawHtml.

    Returns list of (start_hour, start_min, end_hour, end_min) tuples.
    """
    parser = _TextExtractor()
    parser.feed(html)

    group_pattern = re.compile(
        rf"Група\s+{re.escape(group)}\.\s+(.+)", re.IGNORECASE
    )
    time_pattern = re.compile(r"з\s+(\d{1,2}):(\d{2})\s+до\s+(\d{1,2}):(\d{2})")

    for line in parser.lines:
        match = group_pattern.match(line)
        if match:
            rest = match.group(1)
            windows = []
            for m in time_pattern.finditer(rest):
                windows.append((
                    int(m.group(1)), int(m.group(2)),
                    int(m.group(3)), int(m.group(4)),
                ))
            return windows
    return []


class LvivoblenergoProvider(OutageProvider):
    """Outage schedule provider for Lvivoblenergo (LOE)."""

    display_name = "Львівобленерго"

    def __init__(self, group=None):
        self.group = group or os.environ.get("OUTAGE_GROUP", DEFAULT_GROUP)
        self.api_url = SCHEDULE_API_URL

    def fetch_windows(self):
        """Fetch today's outage windows from the Lvivoblenergo API."""
        return self.fetch_days()[date.today()]

    def fetch_days(self):
        """Fetch outage windows for today and, when published, tomorrow."""
        logger.info("Lvivoblenergo: fetching %s (group=%s)", self.api_url, self.group)
        resp = requests.get(self.api_url, timeout=15)
        if not resp.ok:
            body_snippet = resp.text[:200] if resp.text else "(empty)"
            raise OutageFetchError(
                f"Lvivoblenergo API returned HTTP {resp.status_code}: {body_snippet}"
            )

        data = resp.json()
        members = data.get("hydra:member", [])
        if not members:
            raise OutageFetchError("Lvivoblenergo: no hydra:member entries in response")

        items = {item.get("name"): item.get("rawHtml") or ""
                 for item in members[0].get("menuItems", [])}
        if "Today" not in items:
            raise OutageFetchError("Lvivoblenergo: no 'Today' menu item found in response")

        today = date.today()
        result = {today: parse_group_windows(items["Today"], self.group)}
        # "Tomorrow" is empty until LOE publishes it; parse_group_windows can't
        # tell "not published" from "no outages", so only keep it when non-empty.
        tomorrow_windows = parse_group_windows(items.get("Tomorrow", ""), self.group)
        if tomorrow_windows:
            result[today + timedelta(days=1)] = tomorrow_windows
        logger.info("Lvivoblenergo: group %s today %s, tomorrow %s", self.group,
                    result[today], result.get(today + timedelta(days=1), "not published"))
        return result
