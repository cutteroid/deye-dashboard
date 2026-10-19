"""Scan Deye inverter registers to discover available data."""
from pysolarmanv5 import PySolarmanV5
import time
import os

INVERTER_IP = os.environ.get("INVERTER_IP", "0.0.0.0")
LOGGER_SERIAL = int(os.environ.get("LOGGER_SERIAL", "0"))

# Common Deye register map (holding registers)
KNOWN_REGISTERS = {
    # Device info
    3: "Device Type",

    # PV Input
    672: "PV1 Power (W)",
    673: "PV2 Power (W)",
    676: "PV1 Voltage (0.1V)",
    677: "PV1 Current (0.1A)",
    678: "PV2 Voltage (0.1V)",
    679: "PV2 Current (0.1A)",

    # Battery
    586: "Battery Temperature (0.1°C offset 1000)",
    587: "Battery Voltage (0.01V)",
    588: "Battery SOC (%)",
    590: "Battery Power (W, signed, discharge > 0)",
    591: "Battery Current (0.01A, signed, discharge > 0)",

    # Grid
    598: "Grid Voltage L1 (0.1V)",
    599: "Grid Voltage L2 (0.1V)",
    600: "Grid Voltage L3 (0.1V)",
    604: "Grid Frequency (0.01Hz)",
    607: "Grid Power (W, signed)",

    # Load/Output
    633: "Load Voltage (0.1V)",
    634: "Load Current (0.1A)",
    653: "Load Power (W)",

    # Temperatures
    540: "DC Transformer Temp (0.1°C offset 1000)",
    541: "Heat Sink Temp (0.1°C offset 1000)",

    # Daily stats
    502: "Daily Inverter Output (0.1kWh)",
    514: "Daily Battery Charge (0.1kWh)",
    515: "Daily Battery Discharge (0.1kWh)",
    529: "Daily PV Generation (0.1kWh)",
    520: "Daily Grid Import (0.1kWh)",
    521: "Daily Grid Export (0.1kWh)",
    526: "Daily Load (0.1kWh)",
}

print("Scanning Deye inverter registers...")
print("=" * 70)

try:
    inverter = PySolarmanV5(
        address=INVERTER_IP,
        serial=LOGGER_SERIAL,
        port=8899,
        mb_slave_id=1,
        verbose=False,
        socket_timeout=10
    )

    results = {}

    for reg, desc in sorted(KNOWN_REGISTERS.items()):
        try:
            time.sleep(0.1)
            value = inverter.read_holding_registers(reg, 1)[0]

            # Apply scaling/offset for display
            display = value
            if "0.1V" in desc or "0.1A" in desc or "0.1kWh" in desc or "0.1°C" in desc:
                display = value / 10
            elif "0.01V" in desc or "0.01A" in desc or "0.01Hz" in desc:
                display = value / 100
            if "offset 1000" in desc:
                display = (value - 1000) / 10

            results[reg] = value
            print(f"  {reg:4d}: {value:6d}  -> {display:8.1f}  ({desc})")

        except Exception as e:
            print(f"  {reg:4d}: ERROR ({desc})")

    inverter.disconnect()
    print("\n✅ Scan complete")

except Exception as e:
    print(f"❌ Connection error: {e}")
