"""Inverter drivers: one module per kind of inverter, chosen by INVERTER_TYPE.

To add a driver: subclass base.InverterDriver in a new module (read_all_data()
returning the fields documented in base.py, from_settings(), and whatever of
detect_config() / discover() the inverter supports; read_all_data() calls
smooth_battery() on its battery values),
then register it in DRIVERS below.
"""
from .base import (BatterySmoother, InverterConfig, InverterDriver, grid_online,
                   grid_phases_missing, grid_state, to_signed, voltage_to_soc)
from .deye import DeyeInverter

DRIVERS = {driver.name: driver for driver in (DeyeInverter,)}
DEFAULT_DRIVER = "deye"


def driver_class(name=None):
    """Driver class for an INVERTER_TYPE value (empty: the default); ValueError if unknown."""
    name = (name or "").strip().lower() or DEFAULT_DRIVER
    try:
        return DRIVERS[name]
    except KeyError:
        raise ValueError(f"Unknown INVERTER_TYPE={name!r} (available: {', '.join(sorted(DRIVERS))})") from None


def create_inverter(settings):
    """Driver instance for the settings (env / .env: INVERTER_TYPE, INVERTER_IP, ...)."""
    return driver_class(settings.get("INVERTER_TYPE")).from_settings(settings)


__all__ = [
    "BatterySmoother", "DEFAULT_DRIVER", "DRIVERS", "DeyeInverter", "InverterConfig",
    "InverterDriver", "create_inverter", "driver_class", "grid_online", "grid_phases_missing",
    "grid_state", "to_signed", "voltage_to_soc",
]
