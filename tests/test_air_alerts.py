"""Tests for air raid alert providers, poller and /api/alerts."""
import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from air_alerts import (
    DISTRICTS, REGION_CODES, REGION_UIDS, STATUS_MAX_AGE, AlertsFetchError, AlertsInUaProvider,
    AlertsPoller, AlertsProvider, MockAlertsProvider, create_alerts_provider,
)

MAP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "data", "ukraine-regions.json")


class StaticProvider(AlertsProvider):
    display_name = "Test"

    def __init__(self, data=None, error=None):
        self.data, self.error = data, error

    def fetch(self):
        if self.error:
            raise self.error
        return self.data


class TestMapData:
    def test_regions_and_districts(self):
        with open(MAP_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["regions"]) == 27
        assert len(data["districts"]) >= 130  # post-2020 raions + Kyiv + Sevastopol
        assert all(d["region"] in REGION_CODES for d in data["districts"])
        assert all(x["d"].startswith("M") for x in data["regions"] + data["districts"])
        assert all(d["name"]["uk"] and d["name"]["en"] for d in data["districts"])

    def test_alerts_in_ua_uids(self):
        assert REGION_UIDS["UA-30"] == 31 and REGION_UIDS["UA-63"] == 22 and REGION_UIDS["UA-43"] == 29
        assert all(uid is not None for uid in REGION_UIDS.values())
        # Every district outside Crimea has a UID, except the Chornobyl exclusion zone
        missing = [c for c, d in DISTRICTS.items() if d["alerts_uid"] is None and d["region"] != "UA-43"]
        assert missing == ["UA3200"]


def test_factory():
    assert isinstance(create_alerts_provider("mock"), MockAlertsProvider)
    assert isinstance(create_alerts_provider(None), MockAlertsProvider)          # no token: demo
    assert isinstance(create_alerts_provider(None, token="t"), AlertsInUaProvider)  # token: real API
    assert create_alerts_provider("none", token="t") is None
    assert create_alerts_provider("acme") is None  # unknown: disabled, not a crash


def test_mock_is_valid_and_stable_within_slot():
    provider = MockAlertsProvider()
    first, second = provider.fetch(), provider.fetch()
    assert first == second
    assert set(first["regions"]) <= set(REGION_CODES)
    assert first["districts"] and set(first["districts"]) <= set(DISTRICTS)


class TestPoller:
    def test_fills_regions_and_drops_invalid(self):
        poller = AlertsPoller(StaticProvider({"regions": {
            "UA-30": {"status": "alert", "since": "2026-10-17T10:00:00"},
            "UA-99": {"status": "alert"},     # unknown region
            "UA-05": {"status": "maybe"},     # unknown status
        }}))
        poller._fetch()
        status = poller.get_status()
        assert status["status"] == "ok"
        assert len(status["regions"]) == len(REGION_CODES)
        assert status["regions"]["UA-30"]["status"] == "alert"
        assert status["regions"]["UA-05"]["status"] == "none"
        assert "UA-99" not in status["regions"]

    def test_district_alert_makes_region_partial(self):
        poller = AlertsPoller(StaticProvider({
            "regions": {"UA-32": {"status": "alert"}},
            "districts": {
                "UA6312": {"status": "alert"},      # Kharkivskyi raion -> Kharkiv oblast partial
                "UA3202": {"status": "alert"},      # inside a region already under alert
                "UA0502": {"status": "none"},       # "none" entries are not returned
                "UA9999": {"status": "alert"},      # unknown district
            },
        }))
        poller._fetch()
        status = poller.get_status()
        assert status["regions"]["UA-63"]["status"] == "partial"
        assert status["regions"]["UA-32"]["status"] == "alert"  # not downgraded
        assert set(status["districts"]) == {"UA6312", "UA3202"}

    def test_unknown_before_first_fetch(self):
        assert AlertsPoller(StaticProvider({})).get_status()["status"] == "unknown"

    def test_error_reported(self):
        poller = AlertsPoller(StaticProvider(error=AlertsFetchError("API down")))
        poller._fetch()
        assert poller.get_status() == {"provider": "Test", "demo": False, "status": "error", "error": "API down"}

    def test_stale_data_becomes_error(self):
        poller = AlertsPoller(StaticProvider({"regions": {"UA-30": {"status": "alert"}}}))
        poller._fetch()
        poller.provider.error = AlertsFetchError("API down")
        poller._fetch()
        assert poller.get_status()["status"] == "ok"  # recent data survives a failed poll
        poller._last_updated = datetime.now() - STATUS_MAX_AGE - timedelta(seconds=1)
        assert poller.get_status()["status"] == "error"


class TestAlertsInUaProvider:
    @staticmethod
    def _status_string(**chars):
        """Status string with 'N' everywhere except the given {uid: char}."""
        size = max(max(REGION_UIDS.values()), max(d["alerts_uid"] or 0 for d in DISTRICTS.values())) + 1
        s = ["N"] * size
        s[0] = s[1] = s[2] = " "
        for uid, ch in chars.items():
            s[int(uid.lstrip("u"))] = ch
        return "".join(s)

    @staticmethod
    def _response(status_code=200, body=None, headers=None):
        resp = MagicMock(status_code=status_code, ok=status_code < 400, headers=headers or {})
        resp.json.return_value = body
        return resp

    def test_parses_regions_and_districts(self):
        provider = AlertsInUaProvider("secret-token")
        kharkivskyi_uid = DISTRICTS["UA6312"]["alerts_uid"]
        body = self._status_string(u31="A", u22="P", **{f"u{kharkivskyi_uid}": "A"})
        with patch.object(provider._session, "get", return_value=self._response(body=body)) as get:
            result = provider.fetch()
        assert result["regions"]["UA-30"]["status"] == "alert"
        assert result["regions"]["UA-63"]["status"] == "partial"
        assert result["regions"]["UA-05"]["status"] == "none"
        assert result["districts"]["UA6312"]["status"] == "alert"
        url = get.call_args[0][0]
        headers = get.call_args[1]["headers"]
        assert "secret-token" not in url  # token only in the header
        assert headers["Authorization"] == "Bearer secret-token"

    def test_not_modified_reuses_last_result(self):
        provider = AlertsInUaProvider("t")
        first = self._response(body=self._status_string(u31="A"), headers={"Last-Modified": "Sat, 17 Oct 2026 06:00:00 GMT"})
        with patch.object(provider._session, "get", side_effect=[first, self._response(304)]) as get:
            a = provider.fetch()
            b = provider.fetch()
        assert a == b
        assert get.call_args[1]["headers"]["If-Modified-Since"] == "Sat, 17 Oct 2026 06:00:00 GMT"

    @pytest.mark.parametrize("code,fragment", [(401, "token"), (403, "forbidden"), (429, "rate limit"), (500, "HTTP 500")])
    def test_http_errors(self, code, fragment):
        provider = AlertsInUaProvider("t")
        with patch.object(provider._session, "get", return_value=self._response(code)):
            with pytest.raises(AlertsFetchError, match=fragment):
                provider.fetch()

    def test_missing_token(self):
        with pytest.raises(AlertsFetchError, match="ALERTS_IN_UA_TOKEN"):
            AlertsInUaProvider("").fetch()

    def test_unexpected_format(self):
        provider = AlertsInUaProvider("t")
        with patch.object(provider._session, "get", return_value=self._response(body={"alerts": []})):
            with pytest.raises(AlertsFetchError, match="unexpected"):
                provider.fetch()


class TestAlertsEndpoint:
    @pytest.fixture
    def client(self):
        import app as app_module
        app_module.app.config["TESTING"] = True
        orig = app_module.alerts_poller
        with app_module.app.test_client() as c:
            yield c, app_module
        app_module.alerts_poller = orig

    def test_disabled(self, client):
        c, app_module = client
        app_module.alerts_poller = None
        assert c.get("/api/alerts").get_json() == {"status": "disabled"}

    def test_mock_data_flagged_as_demo(self, client):
        c, app_module = client
        poller = AlertsPoller(MockAlertsProvider())
        poller._fetch()
        app_module.alerts_poller = poller
        data = c.get("/api/alerts").get_json()
        assert data["status"] == "ok" and data["demo"] is True
        assert len(data["regions"]) == len(REGION_CODES)
        assert data["districts"]

    def test_page_passes_map_url(self, client):
        c, _ = client
        html = c.get("/").get_data(as_text=True)
        assert "alertsMapUrl: \"/static/data/ukraine-regions.json?v=" in html
        assert 'id="alerts-card"' in html and 'id="alerts-banner"' in html
