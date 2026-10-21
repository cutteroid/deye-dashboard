"""Inverter health fields of the 3-phase driver (state, temperatures, totals, codes)."""
from unittest.mock import MagicMock, patch

import pytest

from inverters import DeyeInverter, InverterConfig
from inverters.deye import bit_codes, inverter_temperature, total_kwh

STATE_NORMAL, STATE_ALARM, STATE_FAULT = 2, 3, 4


def _block(registers, address, count):
    return [registers.get(address + i, 0) for i in range(count)]


@pytest.fixture
def make_inverter():
    """(inverter, registers dict the reads come from)."""
    def make(**overrides):
        registers = {500: STATE_NORMAL, 540: 1385, 541: 1452,          # 38.5 / 45.2 °C
                     516: 0x2710, 517: 0x0001, 518: 0x4E20, 519: 0,      # 7553.6 / 2000.0 kWh
                     553: 0b100, 554: 0, 555: 0b1_0000_0000_0000, 556: 0, 557: 0, 558: 0}
        registers.update(overrides)
        with patch("inverters.deye.PySolarmanV5"):
            inv = DeyeInverter(ip="192.168.1.1", serial=123456,
                               config=InverterConfig(phases=3, has_battery=True))
        inv.read_register = lambda addr: registers.get(addr, 0)
        inv.read_registers = lambda addr, count: _block(registers, addr, count)
        return inv, registers
    return make


def _read(inv):
    data = {}
    with patch("inverters.deye.time.sleep"):
        inv._read_health_3p(data)
    return data


def test_helpers():
    assert inverter_temperature(1385) == pytest.approx(38.5)
    assert inverter_temperature(0) is None                 # -100 °C: not reported
    assert bit_codes([0b101, 0b10], "F") == ["F01", "F03", "F18"]
    assert total_kwh(0x2710, 1) == pytest.approx(7553.6)


def test_normal_inverter(make_inverter):
    inv, _ = make_inverter()
    data = _read(inv)
    assert data["inverter_state"] == "normal"
    assert data["inverter_temperature_dc"] == pytest.approx(38.5)
    assert data["inverter_temperature_ac"] == pytest.approx(45.2)
    assert data["battery_total_charge_kwh"] == pytest.approx(7553.6)
    assert data["battery_total_discharge_kwh"] == pytest.approx(2000.0)
    # Bits are set in the code registers, but a normal inverter shows no codes
    assert data["inverter_warning_codes"] == [] and data["inverter_fault_codes"] == []


@pytest.mark.parametrize("state,name", [(STATE_ALARM, "alarm"), (STATE_FAULT, "fault")])
def test_codes_while_the_inverter_reports_a_problem(make_inverter, state, name):
    inv, registers = make_inverter()
    registers[500] = state
    data = _read(inv)
    assert data["inverter_state"] == name
    assert data["inverter_warning_codes"] == ["W03"]
    assert data["inverter_fault_codes"] == ["F13"]


def test_slow_fields_read_every_few_minutes(make_inverter):
    inv, registers = make_inverter()
    calls = []
    read_registers = inv.read_registers
    inv.read_registers = lambda addr, count: calls.append(addr) or read_registers(addr, count)
    with patch("inverters.deye.time.monotonic", return_value=1000.0):
        _read(inv)
    assert calls == [540, 516]
    registers[540] = 1500                                   # changed, but not read yet
    with patch("inverters.deye.time.monotonic", return_value=1100.0):
        data = _read(inv)
    assert calls == [540, 516] and data["inverter_temperature_dc"] == pytest.approx(38.5)
    with patch("inverters.deye.time.monotonic", return_value=1300.0):
        data = _read(inv)
    assert data["inverter_temperature_dc"] == pytest.approx(50.0)


def test_problem_read_right_away(make_inverter):
    inv, registers = make_inverter()
    with patch("inverters.deye.time.monotonic", return_value=1000.0):
        _read(inv)
        registers[500] = STATE_FAULT
        data = _read(inv)                                   # same moment: not waiting 5 min
    assert data["inverter_fault_codes"] == ["F13"]
    registers[500] = STATE_NORMAL
    with patch("inverters.deye.time.monotonic", return_value=1001.0):
        assert _read(inv)["inverter_fault_codes"] == []     # cleared with the state


def test_failed_health_read_keeps_the_readings(make_inverter):
    inv, _ = make_inverter()
    inv.read_register = lambda addr: (_ for _ in ()).throw(OSError("timeout"))
    data = _read(inv)
    assert data["inverter_state"] is None and data["inverter_fault_codes"] == []


def test_full_read_includes_health(make_inverter):
    inv, registers = make_inverter()
    inv.inverter = MagicMock()                              # an open connection
    with patch("inverters.deye.time.sleep"):
        data = inv._read_3p_data_unlocked()
    assert "error" not in data
    assert data["inverter_state"] == "normal" and data["inverter_temperature_ac"] == pytest.approx(45.2)
