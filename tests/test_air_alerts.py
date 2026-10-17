"""Tests for air raid alert providers, poller and /api/alerts."""
import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from air_alerts import (
    DISTRICTS, REGION_CODES, STATUS_MAX_AGE, AlertsFetchError, AlertsPoller, AlertsProvider,
    MockAlertsProvider, NeptunProvider, create_alerts_provider, normalize_name,
)

MAP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "data", "ukraine-regions.json")

# Trimmed from a live https://neptun.in.ua/api/v1/alerts response
NEPTUN_SAMPLE = {
    "version": 1792246376,
    "updatedAt": "2026-10-17T14:12:56.860825444Z",
    "oblasts": [
        {"key": "автономна республіка крим", "name": "Автономна Республіка Крим",
         "oblast": "Автономна Республіка Крим", "since": "2022-12-10T22:22:00Z", "level": "red"},
        {"key": "луганська", "name": "Луганська область", "oblast": "Луганська область",
         "since": "2022-04-04T16:45:00Z", "level": "red"},
        {"key": "севастополь", "name": "Севастополь", "oblast": "Автономна Республіка Крим",
         "since": "2022-12-10T22:22:00Z", "level": "red"},
        {"key": "київ", "name": "м. Київ", "oblast": "м. Київ", "since": "2026-10-17T13:00:00Z", "level": "yellow"},
    ],
    "raions": [
        {"key": "бахмутський", "name": "Бахмутський район", "oblast": "Донецька область",
         "since": "2026-10-17T10:59:39.322937Z", "level": "yellow", "reasons": ["Дронова загроза (жовтий рівень)"]},
        {"key": "харківський", "name": "Харківський район", "oblast": "Харківська область",
         "since": "2026-10-17T12:00:00Z", "level": "red"},
        {"key": "куп'янський", "name": "Куп’янський район", "oblast": "Харківська область",
         "since": "2026-10-17T12:05:00Z", "level": "yellow"},
        {"key": "червоноградський", "name": "Червоноградський район", "oblast": "Львівська область",
         "since": "2026-10-17T12:10:00Z", "level": "red"},  # pre-2024 name of Sheptytskyi raion
    ],
}


class StaticProvider(AlertsProvider):
    display_name = "Test"

    def __init__(self, data=None, error=None):
        self.data, self.error = data, error

    def fetch(self):
        if self.error:
            raise self.error
        return self.data


def _district(name_uk):
    return next(code for code, d in DISTRICTS.items() if d["name"] == name_uk)


def test_map_data():
    with open(MAP_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["regions"]) == 27
    assert len(data["districts"]) >= 130  # post-2020 raions + Kyiv + Sevastopol
    assert all(d["region"] in REGION_CODES for d in data["districts"])
    assert all(x["d"].startswith("M") for x in data["regions"] + data["districts"])
    assert all(d["name"]["uk"] and d["name"]["en"] for d in data["districts"])


def test_factory():
    assert isinstance(create_alerts_provider(None), NeptunProvider)  # default
    assert isinstance(create_alerts_provider("neptun"), NeptunProvider)
    assert isinstance(create_alerts_provider("mock"), MockAlertsProvider)
    assert create_alerts_provider("none") is None
    assert create_alerts_provider("acme") is None  # unknown: disabled, not a crash


def test_normalize_name():
    assert normalize_name("м. Київ") == "київ"
    assert normalize_name("Куп’янський район") == "куп'янський"
    assert normalize_name("Луганська область") == "луганська"


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

    def test_region_status_derived_from_districts(self):
        poller = AlertsPoller(StaticProvider({
            "regions": {"UA-32": {"status": "alert"}},
            "districts": {
                "UA6312": {"status": "threat"},     # Kharkiv oblast: threat ...
                "UA6308": {"status": "alert"},      # ... and an alert -> partial wins
                "UA1402": {"status": "threat"},     # Donetsk oblast: threat only
                "UA3202": {"status": "alert"},      # inside a region already under alert
                "UA0502": {"status": "none"},       # "none" entries are not returned
                "UA9999": {"status": "alert"},      # unknown district
            },
        }))
        poller._fetch()
        status = poller.get_status()
        assert status["regions"]["UA-63"]["status"] == "partial"
        assert status["regions"]["UA-14"]["status"] == "threat"
        assert status["regions"]["UA-32"]["status"] == "alert"  # not downgraded
        assert set(status["districts"]) == {"UA6312", "UA6308", "UA1402", "UA3202"}

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


class TestNeptunProvider:
    @staticmethod
    def _response(status_code=200, body=None, headers=None):
        resp = MagicMock(status_code=status_code, ok=status_code < 400, headers=headers or {})
        resp.json.return_value = body
        return resp

    def test_parses_live_format(self):
        provider = NeptunProvider()
        with patch.object(provider._session, "get", return_value=self._response(body=NEPTUN_SAMPLE)):
            result = provider.fetch()
        assert result["regions"] == {
            "UA-43": {"status": "alert", "since": "2022-12-10T22:22:00Z"},
            "UA-09": {"status": "alert", "since": "2022-04-04T16:45:00Z"},
            "UA-40": {"status": "alert", "since": "2022-12-10T22:22:00Z"},
            "UA-30": {"status": "threat", "since": "2026-10-17T13:00:00Z"},
        }
        districts = result["districts"]
        assert districts[_district("Бахмутський")]["status"] == "threat"
        assert districts[_district("Харківський")]["status"] == "alert"
        assert districts[_district("Куп'янський")]["status"] == "threat"   # apostrophe variants
        assert districts[_district("Шептицький")]["status"] == "alert"     # old name alias
        assert len(districts) == 4

    def test_every_neptun_raion_alias_exists_on_map(self):
        names = {normalize_name(d["name"]) for d in DISTRICTS.values()}
        assert set(NeptunProvider.RAION_ALIASES.values()) <= names

    def test_unknown_names_ignored(self, caplog):
        provider = NeptunProvider()
        body = {"oblasts": [{"key": "атлантида", "name": "Атлантида", "level": "red"}],
                "raions": [{"key": "невідомий", "name": "Невідомий район", "level": "red"}]}
        with patch.object(provider._session, "get", return_value=self._response(body=body)):
            assert provider.fetch() == {"regions": {}, "districts": {}}
            provider.fetch()
        assert sum("unknown" in r.message for r in caplog.records) == 2  # warned once per name

    def test_not_modified_reuses_last_result(self):
        provider = NeptunProvider()
        first = self._response(body=NEPTUN_SAMPLE, headers={"ETag": 'W/"abc"'})
        with patch.object(provider._session, "get", side_effect=[first, self._response(304)]) as get:
            a = provider.fetch()
            b = provider.fetch()
        assert a == b
        assert get.call_args[1]["headers"]["If-None-Match"] == 'W/"abc"'

    @pytest.mark.parametrize("code,fragment", [(429, "rate limited"), (500, "HTTP 500"), (503, "HTTP 503")])
    def test_http_errors(self, code, fragment):
        provider = NeptunProvider()
        with patch.object(provider._session, "get", return_value=self._response(code)):
            with pytest.raises(AlertsFetchError, match=fragment):
                provider.fetch()

    @pytest.mark.parametrize("body", ["oops", {"alerts": []}, {"oblasts": None, "raions": []}])
    def test_unexpected_format(self, body):
        provider = NeptunProvider()
        with patch.object(provider._session, "get", return_value=self._response(body=body)):
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

    def test_neptun_data_not_demo(self, client):
        c, app_module = client
        provider = NeptunProvider()
        resp = MagicMock(status_code=200, ok=True, headers={})
        resp.json.return_value = NEPTUN_SAMPLE
        with patch.object(provider._session, "get", return_value=resp):
            poller = AlertsPoller(provider)
            poller._fetch()
        app_module.alerts_poller = poller
        data = c.get("/api/alerts").get_json()
        assert data["provider"] == "NEPTUN" and data["demo"] is False
        assert data["regions"]["UA-63"]["status"] == "partial"

    def test_page_passes_map_url(self, client):
        c, _ = client
        html = c.get("/").get_data(as_text=True)
        assert "alertsMapUrl: \"/static/data/ukraine-regions.json?v=" in html
        assert 'id="alerts-card"' in html and 'id="alerts-banner"' in html
        assert html.count('href="https://neptun.in.ua/"') == 2  # attribution in card + fullscreen banner
