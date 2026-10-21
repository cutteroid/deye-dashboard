"""Battery voltage/SOC smoothing over the last full reads (BatterySmoother)."""
from unittest.mock import MagicMock, patch

import pytest

from inverters import BatterySmoother, DeyeInverter, InverterConfig, InverterDriver
from tests.conftest import mock_read_register


class TestBatterySmoother:
    def test_empty(self):
        smoother = BatterySmoother()
        assert smoother.get_voltage() is None and smoother.get_soc() is None

    def test_voltage_average_and_soc_median(self):
        smoother = BatterySmoother()
        for voltage, soc in ((51.0, 50), (52.0, 80), (53.0, 60)):
            smoother.add(voltage, soc)
        assert smoother.get_voltage() == pytest.approx(52.0)
        assert smoother.get_soc() == 60          # sorted [50, 60, 80]

    @pytest.mark.parametrize("voltage", [0, 40.0, 60.0, None])
    def test_implausible_voltage_dropped(self, voltage):
        smoother = BatterySmoother()
        smoother.add(voltage, 75)
        assert smoother.get_voltage() is None and smoother.get_soc() == 75

    @pytest.mark.parametrize("soc", [-1, 150, None])
    def test_implausible_soc_dropped(self, soc):
        smoother = BatterySmoother()
        smoother.add(52.0, soc)
        assert smoother.get_soc() is None and smoother.get_voltage() == pytest.approx(52.0)

    def test_keeps_the_last_six(self):
        smoother = BatterySmoother()
        for i in range(8):
            smoother.add(50.0 + i, 60 + i)
        snap = smoother.snapshot()
        assert snap["voltages"] == [52.0, 53.0, 54.0, 55.0, 56.0, 57.0]
        assert snap["socs"] == [62, 63, 64, 65, 66, 67]
        assert snap["voltage"] == pytest.approx(54.5) and snap["soc"] == 65

    def test_custom_voltage_range(self):
        smoother = BatterySmoother()
        smoother.add(320.0, 70, voltage_range=(100.0, 1000.0))   # HV stack
        assert smoother.get_voltage() == pytest.approx(320.0)


class TestSmoothBattery:
    def test_two_bad_reads_in_a_row_dont_show(self):
        """With 6 reads in the buffer, two glitches (0 V, SOC 0) are outvoted."""
        driver = InverterDriver()
        shown = []
        for voltage, soc in ((52.0, 80), (52.1, 80), (52.2, 81), (0, 0), (0, 0)):
            data = {"battery_voltage": voltage, "battery_soc_raw": soc}
            driver.smooth_battery(data)
            shown.append((round(data["battery_voltage"], 2), data["battery_soc"]))
        assert shown[-1] == (52.1, 80)       # median of [80, 80, 81, 0, 0] is 80
        assert all(soc >= 80 for _, soc in shown)

    def test_first_read_glitch_falls_back_to_raw(self):
        driver = InverterDriver()
        data = {"battery_voltage": 0, "battery_soc_raw": 150}
        driver.smooth_battery(data)
        assert data["battery_voltage"] == 0 and data["battery_soc"] == 150

    def test_uses_the_driver_voltage_range(self):
        class HighVoltage(InverterDriver):
            def battery_voltage_range(self):
                return 100.0, 1000.0
        data = {"battery_voltage": 320.0, "battery_soc_raw": 70}
        HighVoltage().smooth_battery(data)
        assert data["battery_voltage"] == pytest.approx(320.0)
        assert HighVoltage().battery_smoother is not None

    def test_deye_full_read_feeds_the_smoother(self):
        """One full read is the only battery read: its values go into the smoothing."""
        with patch("inverters.deye.PySolarmanV5"):
            inv = DeyeInverter(ip="192.168.1.1", serial=123456,
                               config=InverterConfig(phases=3, has_battery=True))
        inv.inverter = MagicMock()
        values = [{587: 5200, 588: 70}, {587: 5300, 588: 72}, {587: 0, 588: 0}]
        shown = []
        for regs in values:
            inv.read_register = mock_read_register(regs)
            inv.inverter = MagicMock()
            with patch("inverters.deye.time.sleep"):
                data = inv.read_all_data()
            shown.append((round(data["battery_voltage"], 2), data["battery_soc"], data["battery_soc_raw"]))
        assert shown[0] == (52.0, 70, 70)
        assert shown[1] == (52.5, 72, 72)       # average voltage, median of [70, 72]
        assert shown[2] == (52.5, 70, 0)        # 0 V dropped; median of [70, 72, 0]; raw kept
        assert inv.battery_smoother.snapshot()["voltages"] == [52.0, 53.0]
