"""Read-only FlightHub 2 V2 fleet probe (aircraft + remote controllers).

Prints counts per project only: never credentials, serial numbers,
call signs or coordinates. Uses the same environment as the poller
(see flighthub_poller), AERONEXUS_FH_POLL_ENABLED is not required.

    python -m aeronexus.probe_fleet
"""
import asyncio
import os

from .flighthub_poller import FlightHubFleetRefresher, FlightHubPollSettings
from .inventory import DeviceType
from .read_only_transport import (AuthenticationError, BusinessError, NotFoundError,
                                  PermissionDeniedError, ReadOnlyTransportError)
from .status_runtime import StatusRuntime


_HINTS = (
    (AuthenticationError, "HTTP 401: organization key invalid, refreshed, or issued by "
                          "another region (try AERONEXUS_DJI_REGION=eu or us)."),
    (PermissionDeniedError, "HTTP 403: the key's user lacks permission for the project."),
    (NotFoundError, "HTTP 404: route not served by this gateway "
                    "(try AERONEXUS_DJI_API_VERSION=v0.1)."),
)


def _hint(exc: Exception) -> str:
    for cls, text in _HINTS:
        if isinstance(exc, cls):
            return text
    if isinstance(exc, BusinessError):
        return f"FlightHub business error code {exc.business_code}."
    if isinstance(exc, ValueError) and str(exc).startswith("Organization key does not belong"):
        return ("the organization key does not belong to AERONEXUS_DJI_ORGANIZATION_ID; "
                "copy the key of that organization.")
    return ("check AERONEXUS_DJI_PROVIDER/REGION/BASE_URL/TOKEN, project selection, "
            "network and TLS.")


async def probe(environ) -> tuple[StatusRuntime, FlightHubFleetRefresher]:
    settings = FlightHubPollSettings.from_env({**environ, "AERONEXUS_FH_POLL_ENABLED": "1"})
    runtime = StatusRuntime()
    refresher = FlightHubFleetRefresher(runtime, settings)
    await refresher()
    return runtime, refresher


def main() -> int:
    try:
        runtime, refresher = asyncio.run(probe(dict(os.environ)))
    except (ValueError, RuntimeError) as exc:
        # Only our own messages: provider exception text could contain details.
        request = (f" request_id={exc.request_id}"
                   if isinstance(exc, ReadOnlyTransportError) and exc.request_id else "")
        print(f"FlightHub read-only probe failed ({type(exc).__name__}{request}): {_hint(exc)}")
        return 1
    inventory = runtime.inventory
    config = refresher.settings.config
    print(f"FlightHub 2 OpenAPI {config.api_version} ({config.base_url}) - read-only fleet probe")
    for number, project in enumerate(inventory.projects(), 1):
        views = runtime.device_views(project.provider, project.project_id)
        print(f"Project {number}: {len(views)} devices")
        for kind, label in ((DeviceType.AIRCRAFT, "Aircraft"),
                            (DeviceType.CONTROLLER, "Remote controllers")):
            subset = [v for v in views if v["kind"] == kind.value]
            online = sum(v["online"] is True for v in subset)
            offline = sum(v["online"] is False for v in subset)
            print(f"  {label}: {len(subset)} (online {online}, offline {offline}, "
                  f"unknown {len(subset) - online - offline})")
        alerts = [a for v in views for a in v["health"]]
        if refresher.hms_ok is not None:
            print("  HMS alerts: " + ("not available" if refresher.hms_ok is False else
                  f"{sum(a['level'] == 'warning' for a in alerts)} warnings, "
                  f"{len(alerts)} total"))
    print("No DJI state changed. Device IDs, call signs, positions and credentials were not displayed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
