"""Optional local-only WebSocket invalidation channel for Studio browsers.

No upstream DJI socket and no flight commands. Always rely on the same
trusted HTTPS-LAN policy as private Studio endpoints; never put tokens in
WebSocket URLs. A client is notified when the locally cached status changes.
"""
import asyncio
import json
import os

from fastapi import HTTPException, WebSocket
from starlette.websockets import WebSocketDisconnect

from .lan_access import lan_mode_enabled, require_lan


MAX_EVENT_CLIENTS=4


def event_marker(runtime) -> str:
    rows = runtime.device_views()
    # Deliberately omit age_seconds to avoid spurious change events.
    data = [
        (r["provider"],r["project_id"],r["device_id"],
         r["received_at"],r["online"],r["freshness"])
        for r in rows
    ]
    return json.dumps(data,sort_keys=True,separators=(",",":"))


async def serve_studio_events(socket: WebSocket, runtime, state) -> None:
    if os.environ.get("AERONEXUS_STUDIO_EVENTS") != "1" or not lan_mode_enabled():
        await socket.close(code=1008,reason="Event gateway disabled")
        return
    try:
        require_lan(socket)
    except HTTPException:
        await socket.close(code=1008,reason="LAN policy denied")
        return
    if getattr(state,"studio_event_clients",0)>=MAX_EVENT_CLIENTS:
        await socket.close(code=1013,reason="Too many clients")
        return
    state.studio_event_clients=getattr(state,"studio_event_clients",0)+1
    try:
        await socket.accept()
        await socket.send_json({"type":"ready","source":"aeronexus-local-cache",
                                "interval_seconds":3})
        previous=event_marker(runtime)
        await socket.send_json({"type":"fleet_changed"})
        while True:
            # Watch actual disconnects; sleeping without receiving would keep
            # abandoned sockets counted indefinitely when fleet is idle.
            try:
                frame=await asyncio.wait_for(socket.receive(),timeout=3)
            except asyncio.TimeoutError:
                frame=None
            if frame is not None:
                if frame.get("type")=="websocket.disconnect":
                    break
                # No client commands, subscriptions or telemetry writes.
                await socket.close(code=1003,reason="Read-only event stream")
                break
            current=event_marker(runtime)
            if current!=previous:
                previous=current
                await socket.send_json({"type":"fleet_changed"})
    except (WebSocketDisconnect,RuntimeError,OSError):
        pass
    finally:
        state.studio_event_clients=max(0,getattr(state,"studio_event_clients",1)-1)
