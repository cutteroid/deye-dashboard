"""Tests for BatterySampler logic."""
import pytest
from unittest.mock import patch, MagicMock
from inverters import BatterySampler, DeyeInverter, InverterConfig
from tests.conftest import mock_read_register


@pytest.fixture
def sampler():
    """Create a BatterySampler with a mocked inverter."""
    with patch("inverters.deye.PySolarmanV5"):
        inv = DeyeInverter(ip="192.168.1.1", serial=123456)
        inv.inverter = MagicMock()
        inv.config = InverterConfig(phases=3)
        return BatterySampler(inv, interval=10, buffer_size=6)


class TestGetVoltage:
    def test_empty_buffer_returns_none(self, sampler):
        assert sampler.get_voltage() is None

    def test_single_reading(self, sampler):
        sampler._buffer = [51.5]
        assert sampler.get_voltage() == 51.5

    def test_average_of_multiple(self, sampler):
        sampler._buffer = [51.0, 52.0, 53.0]
        assert sampler.get_voltage() == pytest.approx(52.0)


class TestGetSoc:
    def test_empty_buffer_returns_none(self, sampler):
        assert sampler.get_soc() is None

    def test_single_reading(self, sampler):
        sampler._soc_buffer = [75]
        assert sampler.get_soc() == 75

    def test_median_selection(self, sampler):
        sampler._soc_buffer = [50, 80, 60]
        # sorted: [50, 60, 80], middle index 1 → 60
        assert sampler.get_soc() == 60


class TestSample:
    def test_valid_voltage_and_soc_stored(self, sampler):
        """reg 587 returns 5200 (52V), reg 588 returns 75."""
        sampler.inverter.read_register = mock_read_register({587: 5200, 588: 75})
        sampler._sample()
        assert len(sampler._buffer) == 1
        assert sampler._buffer[0] == pytest.approx(52.0)
        assert len(sampler._soc_buffer) == 1
        assert sampler._soc_buffer[0] == 75

    def test_voltage_below_range_discarded(self, sampler):
        """40V is below 46.0V range, should be discarded."""
        sampler.inverter.read_register = mock_read_register({587: 4000, 588: 75})
        sampler._sample()
        assert len(sampler._buffer) == 0
        # SOC should still be stored
        assert len(sampler._soc_buffer) == 1

    def test_voltage_above_range_discarded(self, sampler):
        """60V is above 58.0V range, should be discarded."""
        sampler.inverter.read_register = mock_read_register({587: 6000, 588: 75})
        sampler._sample()
        assert len(sampler._buffer) == 0
        assert len(sampler._soc_buffer) == 1

    def test_soc_out_of_range_discarded(self, sampler):
        """SOC 150 is above 100, should be discarded."""
        sampler.inverter.read_register = mock_read_register({587: 5200, 588: 150})
        sampler._sample()
        assert len(sampler._buffer) == 1
        assert len(sampler._soc_buffer) == 0

    def test_buffer_overflow_evicts_oldest(self, sampler):
        """Fill past buffer_size (6), oldest should be dropped."""
        sampler._buffer = [50.0, 50.5, 51.0, 51.5, 52.0, 52.5]
        sampler.inverter.read_register = mock_read_register({587: 5300, 588: 75})
        sampler._sample()
        assert len(sampler._buffer) == 6
        assert sampler._buffer[0] == 50.5  # oldest (50.0) evicted
        assert sampler._buffer[-1] == pytest.approx(53.0)

    def test_read_failure_no_crash(self, sampler):
        """Exception during read should not propagate."""
        def failing_read(addr):
            raise Exception("connection timeout")

        sampler.inverter.read_register = failing_read
        # Should not raise
        sampler._sample()
        assert len(sampler._buffer) == 0
        assert len(sampler._soc_buffer) == 0


class TestConnectionCleanup:
    def test_driver_disconnects_after_failed_read(self):
        """The Deye driver closes a broken connection, so the next reader reconnects."""
        with patch("inverters.deye.PySolarmanV5"):
            inv = DeyeInverter(ip="192.168.1.1", serial=123456, config=InverterConfig(phases=3))
            inv.inverter = MagicMock()
            inv.read_register = MagicMock(side_effect=Exception("No socket available"))
            inv.disconnect = MagicMock()
            sampler = BatterySampler(inv)
            sampler._sample()           # must not raise
        inv.disconnect.assert_called_once()
        assert sampler._buffer == [] and sampler._soc_buffer == []


class TestDriverIndependence:
    def test_works_with_any_driver(self):
        """The sampler only uses the driver interface (no registers)."""
        from inverters import InverterDriver

        class FakeDriver(InverterDriver):
            def read_battery_sample(self):
                return 51.2, 64

        sampler = BatterySampler(FakeDriver())
        sampler._sample()
        assert sampler.get_voltage() == pytest.approx(51.2) and sampler.get_soc() == 64
