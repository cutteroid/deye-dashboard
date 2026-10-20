"""Brand-neutral inverter layer: config, driver interface, shared helpers.

A driver (see deye.py) talks to one kind of inverter and returns its readings as
a dict with the fields below; everything else (API, dashboard, Telegram bot,
estimates) only uses these fields, never registers or protocols.

Readings returned by InverterDriver.read_all_data() (W, V, A, %, kWh):
    pv1_power, pv2_power, pv_total_power
    battery_voltage, battery_current (> 0 charging), battery_power (> 0 charging),
    battery_soc, battery_soc_raw, battery_status ("Charging"/"Discharging"/"Idle"/"N/A")
    battery_capacity_ah, battery_shutdown_soc   (optional: battery time estimates)
    grid_voltage (L1), grid_power (> 0 importing), grid_status ("Importing"/"Exporting"/"Idle")
    grid_online (house actually on grid power), grid_state (see grid_state())
    load_power
    daily_pv, daily_grid_import, daily_grid_export, daily_load
    generator_power
    3-phase only: grid_voltage_l1..l3, grid_phases_missing, load_l1..l3, voltage_l1..l3
    error (only when the read failed)
"""
import logging
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GRID_ONLINE_MIN_VOLTAGE = 100  # a phase below this has no grid supply


@dataclass
class InverterConfig:
    """What the inverter has (detected by the driver or set in env)."""
    phases: int = 3         # 1 or 3
    has_battery: bool = True
    pv_strings: int = 2     # 1 or 2
    has_generator: bool = False
    device_type: int = None   # driver-specific model code; None until read
    family: str = "unknown"   # driver-specific model family ("unknown": not identified)
    supported: bool = True    # False: the driver knows this model but can't read it

    def to_dict(self):
        return {
            "phases": self.phases,
            "has_battery": self.has_battery,
            "pv_strings": self.pv_strings,
            "has_generator": self.has_generator,
            "device_type": self.device_type,
            "family": self.family,
            "supported": self.supported,
        }


class InverterDriver:
    """Interface of an inverter driver; drivers register in inverters/__init__.py.

    Drivers may be called from several threads (poller, battery sampler, auto-
    detect): anything that uses the connection must hold self.lock.
    """
    name = ""            # INVERTER_TYPE value, e.g. "deye"
    display_name = ""    # shown in the settings when there is more than one driver
    required_settings = ()   # env keys the driver needs, e.g. ("INVERTER_IP",)

    def __init__(self, config=None):
        self.config = config or InverterConfig()
        self.lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings):
        """Driver from the env / .env settings (INVERTER_IP, ...)."""
        raise NotImplementedError

    @classmethod
    def settings_problem(cls, settings):
        """Why these settings can't be used ("" when they're fine): the dashboard
        opens the setup wizard instead of starting the pollers."""
        missing = [key for key in cls.required_settings if not str(settings.get(key) or "").strip()]
        return (" and ".join(missing) + (" are" if len(missing) > 1 else " is") + " required") if missing else ""

    @classmethod
    def discover(cls):
        """Devices on the local network: [{"ip", "model", ...}] (settings wizard scan)."""
        return []

    def read_all_data(self, battery_sampler=None):
        """Readings (see the module docstring); on failure {"error": message}."""
        raise NotImplementedError

    def detect_config(self):
        """Detect capabilities (blocking, may take seconds); default: keep the current ones."""
        return InverterConfig(**self.config.to_dict())

    def read_device_type(self):
        """(model code or None, family) of the connected inverter; never raises."""
        return None, "unknown"

    def family_supported(self, family):
        """Can this driver read inverters of this family?"""
        return True

    def read_battery_sample(self):
        """(battery voltage, SOC %) for BatterySampler; raises on failure."""
        raise NotImplementedError

    def battery_voltage_range(self):
        """Plausible battery voltage; BatterySampler discards readings outside it."""
        return 46.0, 58.0   # 48 V LiFePO4 (16S)


def grid_online(voltages, connected=None):
    """Is the house actually on grid power?

    connected: the inverter's own "grid connected" state (e.g. its grid relay),
    the ground truth when it has one: when it disconnects (a phase out of range,
    or cut by a smart meter) the house runs on battery although the other phases
    still show voltage. None (unknown): every phase must have supply.
    """
    if connected is not None:
        return bool(connected)
    present = [v for v in voltages if v is not None]
    return bool(present) and all(v >= GRID_ONLINE_MIN_VOLTAGE for v in present)


def grid_state(online, voltages):
    """"online", or why not: "partial" (some phases without supply), "out_of_range"
    (all phases present but the inverter stays disconnected, e.g. voltage or
    frequency out of limits) or "outage" (no supply at all)."""
    if online:
        return "online"
    present = [v >= GRID_ONLINE_MIN_VOLTAGE for v in voltages if v is not None]
    if not any(present):
        return "outage"
    return "out_of_range" if all(present) else "partial"


def grid_phases_missing(voltages):
    """Phase numbers (1-based) without supply, e.g. [2] for "L2 DOWN"."""
    return [i + 1 for i, v in enumerate(voltages) if v is not None and v < GRID_ONLINE_MIN_VOLTAGE]


def to_signed(value):
    """Unsigned 16-bit register value -> signed."""
    if value >= 32768:
        return value - 65536
    return value


LIFEPO4_16S_CURVE = [
    (57.6, 100), (56.0, 99), (54.4, 95), (53.6, 90),
    (53.2, 80), (52.8, 70), (52.4, 60), (52.0, 50),
    (51.6, 40), (51.2, 30), (50.4, 17), (48.0, 0),
]


def voltage_to_soc(voltage):
    """Convert LiFePO4 16S battery voltage to SOC using discharge curve."""
    if voltage >= LIFEPO4_16S_CURVE[0][0]:
        return 100
    if voltage <= LIFEPO4_16S_CURVE[-1][0]:
        return 0
    # Find the two points to interpolate between
    for i in range(len(LIFEPO4_16S_CURVE) - 1):
        v_high, soc_high = LIFEPO4_16S_CURVE[i]
        v_low, soc_low = LIFEPO4_16S_CURVE[i + 1]
        if voltage >= v_low:
            ratio = (voltage - v_low) / (v_high - v_low)
            return int(soc_low + ratio * (soc_high - soc_low))
    return 0


class BatterySampler:
    """Reads battery voltage/SOC periodically (via the driver) and provides smoothed values."""

    def __init__(self, inverter, interval=10, buffer_size=6):
        self.inverter = inverter
        self.interval = interval
        self.buffer_size = buffer_size
        self._buffer = []
        self._soc_buffer = []
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def _sample(self):
        """Read battery voltage and SOC once, store if valid."""
        try:
            voltage, raw_soc = self.inverter.read_battery_sample()
        except Exception as e:
            logger.warning("BatterySampler: failed to read battery: %s", e)
            return

        low, high = self.inverter.battery_voltage_range()
        with self._lock:
            if low <= voltage <= high:
                self._buffer.append(voltage)
                if len(self._buffer) > self.buffer_size:
                    self._buffer.pop(0)
            else:
                logger.warning("BatterySampler: discarding implausible voltage %.2fV", voltage)

            if 0 <= raw_soc <= 100:
                self._soc_buffer.append(raw_soc)
                if len(self._soc_buffer) > self.buffer_size:
                    self._soc_buffer.pop(0)
            else:
                logger.warning("BatterySampler: discarding implausible SOC %d%%", raw_soc)

    def get_voltage(self):
        """Return averaged voltage from buffer, or None if no valid readings."""
        with self._lock:
            if not self._buffer:
                return None
            return sum(self._buffer) / len(self._buffer)

    def get_soc(self):
        """Return the median SOC of the buffer (rejects outliers), or None."""
        with self._lock:
            if not self._soc_buffer:
                return None
            return sorted(self._soc_buffer)[len(self._soc_buffer) // 2]

    def _run(self):
        """Main sampling loop (idle while no battery is configured)."""
        while self._running:
            # Checked every loop: background auto-detect may change the config
            if self.inverter.config.has_battery:
                self._sample()
            time.sleep(self.interval)

    def start(self):
        """Start sampling in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop sampling."""
        self._running = False
