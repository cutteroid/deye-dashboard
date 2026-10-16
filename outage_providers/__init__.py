"""Outage schedule providers package."""
from outage_providers.base import (
    OutageProvider,
    OutageFetchError,
    OutageSchedulePoller,
    create_outage_provider,
    BATTERY_CAPACITY_KWH,
)
