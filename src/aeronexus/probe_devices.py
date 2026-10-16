"""Read-only DJI aircraft discovery. No credentials are printed or persisted.

Usage:
    python -m aeronexus.probe_devices --provider public
    python -m aeronexus.probe_devices --provider onprem

Environment:
    AERONEXUS_DJI_BASE_URL  HTTPS origin
    AERONEXUS_DJI_TOKEN     Organization OpenAPI key
    AERONEXUS_DJI_PROJECT_UUID  required for Public Cloud
    AERONEXUS_DJI_ORGANIZATION_UUID  required for On-Premises
"""
import argparse
import asyncio
import os

from .flighthub_device_list import read_public_aircraft, read_onprem_aircraft
from .providers import ProviderConfig, ProviderKind


async def probe(provider: str, values: dict[str, str], *, page: int = 1,
                page_size: int = 20) -> tuple[int, int, int]:
    kind = {"public": ProviderKind.PUBLIC_V2,
            "onprem": ProviderKind.ONPREM_V2}[provider]
    config = ProviderConfig(kind, values["AERONEXUS_DJI_BASE_URL"],
                            values["AERONEXUS_DJI_TOKEN"])
    if kind == ProviderKind.PUBLIC_V2:
        observations = await read_public_aircraft(
            config, values["AERONEXUS_DJI_PROJECT_UUID"])
    else:
        observations = await read_onprem_aircraft(
            config, values["AERONEXUS_DJI_ORGANIZATION_UUID"],
            page=page, page_size=page_size)
    return (len(observations),
            sum(item.online is True for item in observations),
            sum(item.online is None for item in observations))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only DJI FlightHub V2 aircraft probe (counts only)")
    parser.add_argument("--provider", choices=("public", "onprem"), required=True)
    parser.add_argument("--page", type=int, default=1,
                        help="On-Premises page (default: 1)")
    parser.add_argument("--page-size", type=int, default=20,
                        help="On-Premises page size (default: 20)")
    args = parser.parse_args(argv)
    required = ["AERONEXUS_DJI_BASE_URL", "AERONEXUS_DJI_TOKEN"]
    required.append("AERONEXUS_DJI_PROJECT_UUID" if args.provider == "public"
                    else "AERONEXUS_DJI_ORGANIZATION_UUID")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        parser.error("Missing environment variables: " + ", ".join(missing))
    try:
        count, online, unknown = asyncio.run(
            probe(args.provider, dict(os.environ),
                  page=args.page, page_size=args.page_size))
    except (ValueError, RuntimeError) as exc:
        # Do not print HTTP response bodies, headers, URLs or tokens.
        print(f"DJI read-only probe failed ({type(exc).__name__}); "
              "check endpoint, permissions, TLS and provider configuration.")
        return 1
    print(f"Provider: {args.provider}")
    print(f"Aircraft on this page: {count}")
    print(f"Online: {online}; Offline: {count - online - unknown}; "
          f"Unknown: {unknown}")
    print("No DJI state changed. Device IDs and credentials were not displayed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
