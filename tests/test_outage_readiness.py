"""Outage readiness: will the battery last through the next planned outage?"""
from datetime import datetime
from unittest.mock import patch

import pytest

from outage_readiness import BATTERY_LOSS_FACTOR, merged_windows, next_outage, outage_readiness

NOW = datetime(2026, 10, 21, 12, 0)
CAPACITY_WH = 10240                      # 10.24 kWh


def _at(h, m=0, day=21):
    return datetime(2026, 10, day, h, m)


def _days(*windows):
    return [{"windows": list(windows)}]


def _data(soc=80, shutdown=20, charge_minutes=None):
    return {"battery_soc": soc, "battery_shutdown_soc": shutdown, "battery_charge_minutes": charge_minutes}


def test_touching_windows_are_one_outage():
    days = [{"windows": [(_at(16), _at(18)), (_at(14), _at(16))]},
            {"windows": [(_at(0, day=22), _at(4, day=22))]}]
    assert merged_windows(days) == [(_at(14), _at(18)), (_at(0, day=22), _at(4, day=22))]
    assert next_outage(days, NOW) == (_at(14), _at(18))
    assert next_outage(days, _at(19)) == (_at(0, day=22), _at(4, day=22))   # tomorrow's
    assert next_outage(days, _at(5, day=22)) is None


def test_no_outage():
    assert outage_readiness(_data(), _days((_at(8), _at(10))), NOW, 400, CAPACITY_WH) == {"status": "no_outage"}


def test_enough():
    # 14:00-18:00 at 400 W: 4 h x 440 W = 1.76 kWh; 80% -> 20% of 10.24 kWh = 6.14 kWh
    r = outage_readiness(_data(), _days((_at(14), _at(18))), NOW, 400, CAPACITY_WH)
    assert r["status"] == "ok" and r["verdict"] == "enough" and r["during"] is False
    assert r["starts_in_minutes"] == 120 and r["outage_minutes"] == 240
    assert r["needed_kwh"] == pytest.approx(1.76) and r["available_kwh"] == pytest.approx(6.14, abs=0.01)
    assert r["lasts_minutes"] == round(6144 / (400 * BATTERY_LOSS_FACTOR) * 60)
    assert r["short_minutes"] is None


def test_tight_and_short():
    window = _days((_at(14), _at(22)))                     # 8 h
    tight = outage_readiness(_data(soc=55), window, NOW, 400, CAPACITY_WH)   # 3.58 vs 3.52 kWh
    assert tight["verdict"] == "tight"
    short = outage_readiness(_data(soc=40), window, NOW, 400, CAPACITY_WH)   # 2.05 vs 3.52 kWh
    assert short["verdict"] == "short"
    assert short["short_minutes"] == short["outage_minutes"] - short["lasts_minutes"] > 0


def test_during_an_outage_counts_the_rest():
    r = outage_readiness(_data(soc=50), _days((_at(10), _at(14))), NOW, 400, CAPACITY_WH)
    assert r["during"] is True and r["starts_in_minutes"] is None
    assert r["outage_minutes"] == 120 and r["needed_kwh"] == pytest.approx(0.88)


def test_charging_before_the_outage():
    # 50% now, full in 4 h; the outage starts in 2 h -> ~75% at its start
    r = outage_readiness(_data(soc=50, charge_minutes=240), _days((_at(14), _at(18))), NOW, 400, CAPACITY_WH)
    assert r["soc"] == 50 and r["soc_at_start"] == 75


def test_unknown_capacity():
    r = outage_readiness(_data(), _days((_at(14), _at(18))), NOW, 400, None)
    assert r["status"] == "no_data" and r["start"] == _at(14).isoformat()


class TestEndpoint:
    @pytest.fixture
    def client(self):
        import app as app_module
        app_module.app.config["TESTING"] = True
        saved = (app_module.outage_poller, app_module.inverter_poller, app_module.inverter_config)
        with app_module.app.test_client() as c:
            yield c, app_module
        app_module.outage_poller, app_module.inverter_poller, app_module.inverter_config = saved

    def test_disabled_without_schedule(self, client):
        c, app_module = client
        app_module.outage_poller = None
        assert c.get("/api/outage-readiness").get_json() == {"status": "disabled"}

    def test_readiness(self, client):
        from unittest.mock import MagicMock
        from inverters import InverterConfig
        c, app_module = client
        app_module.inverter_config = InverterConfig(phases=3, has_battery=True)
        app_module.outage_poller = MagicMock()
        app_module.outage_poller.get_outage_status.return_value = {
            "status": "upcoming", "days": [{"date": NOW.date(), "windows": [(_at(14), _at(18))]}]}
        app_module.inverter_poller = MagicMock(data={"battery_soc": 80, "battery_shutdown_soc": 20,
                                                     "load_average_w": 400, "battery_capacity_ah": 200,
                                                     "battery_voltage": 51.2})
        with patch("app.datetime") as fake_datetime:
            fake_datetime.now.return_value = NOW
            r = c.get("/api/outage-readiness").get_json()
        assert r["verdict"] == "enough" and r["average_load_w"] == 400
        assert r["available_kwh"] == pytest.approx(6.14, abs=0.01)    # 200 Ah x 51.2 V x 60%
