"""Inverter driver system: registry, factory, settings checks, base interface."""
from unittest.mock import patch

import pytest

import inverters
from inverters import (DRIVERS, DeyeInverter, InverterConfig, InverterDriver, create_inverter,
                       driver_class, grid_online)


class TestRegistry:
    def test_deye_is_the_default(self):
        assert inverters.DEFAULT_DRIVER in DRIVERS
        assert driver_class(None) is DeyeInverter
        assert driver_class("") is DeyeInverter
        assert driver_class(" Deye ") is DeyeInverter

    def test_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown INVERTER_TYPE='acme'"):
            driver_class("acme")

    def test_every_driver_implements_the_interface(self):
        for name, driver in DRIVERS.items():
            assert issubclass(driver, InverterDriver) and driver.name == name
            assert driver.display_name and driver.required_settings
            for method in ("from_settings", "read_all_data"):
                assert getattr(driver, method) is not getattr(InverterDriver, method), (name, method)

    def test_setup_script_knows_every_driver(self):
        """setup.py (stdlib only, can't import the drivers) keeps its own list."""
        import setup
        assert set(setup.INVERTER_TYPES) == set(DRIVERS)


class TestFactory:
    def test_create_from_settings(self):
        with patch("inverters.deye.PySolarmanV5"):
            inv = create_inverter({"INVERTER_IP": "192.168.1.100", "LOGGER_SERIAL": "1234567890"})
        assert isinstance(inv, DeyeInverter) and (inv.ip, inv.serial) == ("192.168.1.100", 1234567890)

    def test_bad_serial_does_not_crash(self):
        inv = create_inverter({"INVERTER_TYPE": "deye", "INVERTER_IP": "1.2.3.4", "LOGGER_SERIAL": "abc"})
        assert inv.serial == 0


class TestSettingsProblem:
    @pytest.mark.parametrize("settings,problem", [
        ({"INVERTER_IP": "1.2.3.4", "LOGGER_SERIAL": "42"}, ""),
        ({}, "INVERTER_IP and LOGGER_SERIAL are required"),
        ({"INVERTER_IP": "0.0.0.0", "LOGGER_SERIAL": "42"}, "INVERTER_IP is required"),
        ({"INVERTER_IP": "1.2.3.4", "LOGGER_SERIAL": "99999999999"}, "LOGGER_SERIAL must be"),
    ])
    def test_deye(self, settings, problem):
        result = DeyeInverter.settings_problem(settings)
        assert result.startswith(problem) if problem else result == ""

    def test_unknown_type_is_not_configured(self):
        from app import is_configured
        env = {"INVERTER_TYPE": "acme", "INVERTER_IP": "1.2.3.4", "LOGGER_SERIAL": "42"}
        with patch.dict("os.environ", env):
            assert is_configured() is False


class TestBaseDriver:
    def test_defaults(self):
        driver = InverterDriver(InverterConfig(phases=1))
        assert driver.discover() == []
        assert driver.read_device_type() == (None, "unknown")
        assert driver.family_supported("anything") is True
        assert driver.detect_config() == InverterConfig(phases=1)   # keeps what it has
        with pytest.raises(NotImplementedError):
            driver.read_all_data()

    def test_grid_online(self):
        assert grid_online([230, 231, 229]) is True
        assert grid_online([230, 0, 229]) is False                  # a phase without supply
        assert grid_online([230, 231, 229], connected=False) is False  # inverter disconnected
        assert grid_online([], connected=None) is False


class TestUi:
    @pytest.fixture
    def client(self):
        import app as app_module
        app_module.app.config["TESTING"] = True
        with app_module.app.test_client() as c:
            yield c

    def test_page_has_no_brand(self, client):
        html = client.get("/").get_data(as_text=True)
        assert "deye" not in html.lower() and "solarman" not in html.lower()

    def test_type_list_only_with_several_drivers(self, client):
        html = client.get("/").get_data(as_text=True)
        assert "inverterTypes: []" in html            # one driver: nothing to choose

    def test_locales_have_no_brand(self):
        import json
        import os
        root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")
        for name in os.listdir(root):
            text = open(os.path.join(root, name), encoding="utf-8").read().lower()
            assert "deye" not in text and "solarman" not in text, name
