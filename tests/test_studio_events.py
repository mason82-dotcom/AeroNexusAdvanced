"""No live event access outside explicitly opted-in HTTPS LAN."""
import asyncio
from types import SimpleNamespace

import pytest
from starlette.websockets import WebSocketDisconnect

from aeronexus import studio_events


class FakeWebSocket:
    def __init__(self, *, ip="192.168.178.44",scheme="wss",
                 host="192.168.178.63",origin="https://192.168.178.63:8000"):
        self.scope={"type":"websocket"}
        self.client=SimpleNamespace(host=ip)
        self.url=SimpleNamespace(scheme=scheme,hostname=host,port=8000)
        self.headers={"origin":origin,"sec-fetch-site":"same-origin"} if origin else {}
        self.messages=[]
        self.closed=None
        self.accepted=False

    async def close(self,*,code,reason):
        self.closed=(code,reason)

    async def accept(self):
        self.accepted=True

    async def send_json(self,value):
        self.messages.append(value)

    async def receive(self):
        return {"type":"websocket.disconnect"}


class FakeRuntime:
    row={"provider":"test","project_id":"p","device_id":"D","received_at":"2026-10-16T10:00:00Z","online":True,"freshness":"fresh"}
    def device_views(self):
        return (self.row.copy(),)


def run(ws):
    return asyncio.run(studio_events.serve_studio_events(
        ws,FakeRuntime(),SimpleNamespace(studio_event_clients=0)))


def test_events_disabled_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("AERONEXUS_STUDIO_EVENTS",raising=False)
    monkeypatch.setenv("AERONEXUS_LAN_NO_TOKEN","1")
    assert run(FakeWebSocket()) is None


@pytest.mark.parametrize("bad",[
    {"ip":"8.8.8.8"},
    {"host":"evil.example"},
    {"scheme":"ws"},
    {"origin":""},
    {"origin":"https://other.example:8000"}
])
def test_events_refuse_invalid_lan_connections(monkeypatch,bad):
    monkeypatch.setenv("AERONEXUS_STUDIO_EVENTS","1")
    monkeypatch.setenv("AERONEXUS_LAN_NO_TOKEN","1")
    monkeypatch.setenv("AERONEXUS_LAN_HOST","192.168.178.63")
    ws=FakeWebSocket(**bad)
    run(ws)
    assert ws.accepted is False
    assert ws.closed and ws.closed[0]==1008


def test_events_require_token_free_trusted_lan_not_bearer_url(monkeypatch):
    monkeypatch.setenv("AERONEXUS_STUDIO_EVENTS","1")
    monkeypatch.delenv("AERONEXUS_LAN_NO_TOKEN",raising=False)
    ws=FakeWebSocket()
    run(ws)
    assert not ws.accepted
    assert ws.closed[0]==1008


def test_events_emit_only_cache_invalidation_and_limit_clients(monkeypatch):
    monkeypatch.setenv("AERONEXUS_STUDIO_EVENTS","1")
    monkeypatch.setenv("AERONEXUS_LAN_NO_TOKEN","1")
    monkeypatch.setenv("AERONEXUS_LAN_HOST","192.168.178.63")
    ws=FakeWebSocket()
    state=SimpleNamespace(studio_event_clients=0)
    calls=0
    runtime=FakeRuntime()
    async def mock_receive():
        nonlocal calls
        calls+=1
        if calls==1:
            runtime.row={**runtime.row,"received_at":"2026-10-16T10:00:01Z"}
            raise asyncio.TimeoutError()
        return {"type":"websocket.disconnect"}
    ws.receive=mock_receive
    asyncio.run(studio_events.serve_studio_events(ws,runtime,state))
    assert ws.accepted and ws.closed is None
    assert [msg["type"] for msg in ws.messages]==[
        "ready","fleet_changed","fleet_changed"]
    assert state.studio_event_clients==0
    assert all("battery_percent" not in str(message) for message in ws.messages)
    limited=SimpleNamespace(studio_event_clients=studio_events.MAX_EVENT_CLIENTS)
    other=FakeWebSocket()
    asyncio.run(studio_events.serve_studio_events(other,runtime,limited))
    assert other.closed and other.closed[0]==1013
    # An attempted client command immediately terminates this read-only stream.
    cmd=FakeWebSocket()
    async def command():
        return {"type":"websocket.receive","text":"{\"command\":\"takeoff\"}"}
    cmd.receive=command
    asyncio.run(studio_events.serve_studio_events(cmd,runtime,SimpleNamespace(studio_event_clients=0)))
    assert cmd.closed[0]==1003
