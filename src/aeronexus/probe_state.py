"""Read-only FlightHub 2 Public Cloud aircraft-state probe.

Outputs telemetry summaries only: never credentials, serial number or GPS
coordinates. A project/device is read from environment, not CLI arguments.
"""
import asyncio
import os

from .flighthub_device_state import read_public_aircraft_state
from .providers import ProviderConfig, ProviderKind


_REQUIRED = (
    "AERONEXUS_DJI_BASE_URL",
    "AERONEXUS_DJI_TOKEN",
    "AERONEXUS_DJI_PROJECT_UUID",
    "AERONEXUS_DJI_DEVICE_SN",
)


async def probe(values: dict[str, str]):
    config = ProviderConfig(
        ProviderKind.PUBLIC_V2,
        values["AERONEXUS_DJI_BASE_URL"],
        values["AERONEXUS_DJI_TOKEN"],
    )
    return await read_public_aircraft_state(
        config,
        values["AERONEXUS_DJI_PROJECT_UUID"],
        values["AERONEXUS_DJI_DEVICE_SN"],
    )


def main() -> int:
    missing = [key for key in _REQUIRED if not os.environ.get(key)]
    if missing:
        print("Required environment variables missing: " + ", ".join(missing))
        return 2
    try:
        snapshot = asyncio.run(probe(dict(os.environ)))
    except (ValueError, RuntimeError):
        print("Read-only DJI state probe failed; check permissions, endpoint, "
              "project, device ID, TLS and response format.")
        return 1
    status = "unknown" if snapshot.online is None else (
        "online" if snapshot.online else "offline"
    )
    print("DJI FlightHub Public Cloud V2 — read-only aircraft state")
    print(f"Status: {status}")
    for name, value, unit in (
        ("Battery", snapshot.battery_percent, "%"),
        ("Height", snapshot.height_m, "m"),
        ("Horizontal speed", snapshot.horizontal_speed_mps, "m/s"),
        ("Vertical speed", snapshot.vertical_speed_mps, "m/s"),
        ("Total flight time", snapshot.total_flight_time_s, "s"),
        ("Flight count", snapshot.total_flight_sorties, ""),
        ("GPS satellites", snapshot.gps_satellites, ""),
        ("RTK satellites", snapshot.rtk_satellites, ""),
        ("Battery voltage", snapshot.battery_voltage_mv, "mV"),
        ("Battery temperature", snapshot.battery_temperature_c, "C"),
    ):
        print(f"{name}: {value if value is not None else 'not available'}"
              f"{(' ' + unit) if value is not None and unit else ''}")
    location = snapshot.latitude is not None and snapshot.longitude is not None
    print(f"GPS coordinates present: {'yes' if location else 'no'} (not displayed)")
    print("RTK state: " + ("not available" if snapshot.rtk_state is None else
                           "raw DJI state available (not interpreted as RTK fix)"))
    print("No DJI settings or flight commands were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
