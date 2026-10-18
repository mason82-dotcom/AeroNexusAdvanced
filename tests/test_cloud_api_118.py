"""Cloud API properties and deterministic per-field source/receive clocks."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import importlib
import json

import pytest
from fastapi.testclient import TestClient

from aeronexus.cloud_api_details import normalize_details, validate_details
from aeronexus.cloud_api_mqtt import CloudOsdIngest
from aeronexus.cloud_api_osd import normalize_osd, osd_envelope
from aeronexus.inventory import DeviceType
from aeronexus.providers import ProviderKind
from aeronexus.status_runtime import StatusRuntime
from aeronexus.telemetry_sync import parse_snapshot


NOW = datetime(2026, 10, 17, 17, 44, tzinfo=timezone.utc)
DRONE, RC = 'TESTDRONE', 'TESTRC'
CLOUD = ProviderKind.CLOUD_API


@pytest.fixture
def feed(monkeypatch):
    clock = [NOW]
    monkeypatch.setattr('aeronexus.cloud_api_mqtt.utc_now', lambda: clock[0])
    return CloudOsdIngest(StatusRuntime()), clock


def push(feed, data, *, device=DRONE, channel='osd', source=None, missing=False):
    ingest, clock = feed
    packet = {'data': data}
    if not missing:
        packet['timestamp'] = int((source or clock[0]).timestamp() * 1000)
    return ingest.handle(f'thing/product/{device}/{channel}', json.dumps(packet).encode(), allow_state=True)


def view(feed, device=DRONE):
    ingest, clock = feed
    return next(v for v in ingest.runtime.device_views(now=clock[0]) if v['device_id'] == device)


def test_state_does_not_renew_old_position_battery_or_device_liveness(feed):
    assert push(feed, {'mode_code': 3, 'latitude': 49., 'longitude': 8.,
                       'battery': {'capacity_percent': 80}})
    feed[1][0] += timedelta(minutes=10)
    assert push(feed, {'position_state': {'quality': 10}}, channel='state')
    v = view(feed)
    assert v['freshness'] == 'stale' and v['online'] is None
    assert v['telemetry']['battery_percent'] is v['telemetry']['latitude'] is None
    assert v['last_known_telemetry']['battery_percent'] == 80
    assert v['telemetry']['cloud_details']['position']['quality_code'] == 10
    assert v['field_status']['battery_percent']['freshness'] == 'stale'
    assert v['field_status']['cloud_details.position.quality_code']['channel'] == 'state'


def test_partial_osd_refreshes_only_present_fields(feed):
    push(feed, {'mode_code': 3, 'battery': {'capacity_percent': 80}})
    feed[1][0] += timedelta(minutes=10)
    assert push(feed, {'attitude_head': 25})  # known aircraft, no classifier key
    v = view(feed)
    assert v['freshness'] == 'fresh' and v['online'] is True
    assert v['telemetry']['battery_percent'] is None
    assert v['telemetry']['cloud_details']['heading_deg'] == 25


def test_older_duplicate_equal_conflicting_and_undated_samples_cannot_overwrite(feed):
    push(feed, {'mode_code': 3, 'battery': {'capacity_percent': 80}})
    assert not push(feed, {'mode_code': 3, 'battery': {'capacity_percent': 80}})
    assert not push(feed, {'battery': {'capacity_percent': 1}})
    assert not push(feed, {'battery': {'capacity_percent': 2}}, source=NOW-timedelta(seconds=1))
    assert not push(feed, {'battery': {'capacity_percent': 3}}, missing=True)
    assert view(feed)['telemetry']['battery_percent'] == 80
    assert feed[0].outdated == 4


def test_equal_source_time_can_add_disjoint_partial_fields_without_renewing_online(feed):
    push(feed, {'mode_code': 3})
    feed[1][0] += timedelta(seconds=10)
    assert push(feed, {'attitude_head': 25}, source=NOW)
    v = view(feed)
    assert v['age_seconds'] == 10
    assert v['field_status']['cloud_details.heading_deg']['source_age_seconds'] == 10


def test_cross_channel_ordering_preserves_newer_property(feed):
    push(feed, {'mode_code': 3, 'position_state': {'is_fixed': 1}})
    feed[1][0] += timedelta(seconds=5)
    push(feed, {'position_state': {'is_fixed': 2}}, channel='state')
    feed[1][0] += timedelta(seconds=5)
    assert push(feed, {'mode_code': 9, 'position_state': {'is_fixed': 0}}, source=NOW+timedelta(seconds=2))
    v = view(feed)
    assert v['telemetry']['flight_mode_code'] == 9
    assert v['telemetry']['rtk_state'] == 'is_fixed:2'


def test_old_first_sample_is_stale_and_future_source_is_not_fresh(feed):
    assert push(feed, {'mode_code': 3}, source=NOW-timedelta(minutes=10))
    assert view(feed)['freshness'] == 'stale'
    assert not push(feed, {'mode_code': 4}, source=NOW+timedelta(seconds=31))
    assert push(feed, {'mode_code': 4}, source=NOW+timedelta(seconds=5))
    assert view(feed)['freshness'] == 'clock_skew'
    assert view(feed)['telemetry']['flight_mode_code'] is None


def test_undated_legacy_packets_use_receive_age_and_expire(feed):
    assert push(feed, {'mode_code': 3}, missing=True)
    assert view(feed)['field_status']['flight_mode_code']['source_timestamp_ms'] is None
    feed[1][0] += timedelta(seconds=91)
    assert view(feed)['telemetry']['flight_mode_code'] is None


def test_invalid_later_packet_does_not_advance_clocks_or_partially_commit(feed):
    push(feed, {'mode_code': 3})
    old_clocks = dict(feed[0].runtime.cloud_field_clocks)
    feed[1][0] += timedelta(seconds=5)
    assert not push(feed, {'mode_code': 4, 'battery': {'capacity_percent': 200}})
    assert feed[0].runtime.cloud_field_clocks == old_clocks
    assert push(feed, {'mode_code': 5}, source=NOW+timedelta(seconds=1))
    assert view(feed)['telemetry']['flight_mode_code'] == 5


def test_dynamic_payloads_are_merged_by_leaf_without_erasing_other_payloads(feed):
    push(feed, {'mode_code': 3, '89-0-0': {'gimbal_pitch': -90, 'gimbal_roll': 0},
                '88-0-0': {'zoom_factor': 5}})
    feed[1][0] += timedelta(seconds=1)
    assert push(feed, {'89-0-0': {'gimbal_yaw': 45}})
    p = view(feed)['telemetry']['cloud_details']['payloads']
    assert p['89-0-0'] == {'gimbal_pitch_deg': -90, 'gimbal_roll_deg': 0, 'gimbal_yaw_deg': 45}
    assert p['88-0-0']['zoom_factor'] == 5


def test_rc_only_status_registers_and_preserves_wireless_and_height(feed):
    assert push(feed, {'live_status': [{'video_id': 'private-serial/path', 'video_type': 'normal',
                                      'status': 1, 'error_status': 0}]}, device=RC)
    feed[1][0] += timedelta(seconds=1)
    assert push(feed, {'height': 150, 'wireless_link': {'sdr_quality': 5, 'sdr_freq_band': 2.4}}, device=RC)
    d = view(feed, RC)['telemetry']['cloud_details']
    assert d['wireless_link']['sdr_quality'] == 5 and d['controller_height_m'] == 150
    assert d['live_status'][0]['status_code'] == 1
    assert 'private-serial' not in json.dumps(d)


def test_property_units_bounds_and_privacy():
    raw = {'wind_speed': 123, 'wind_direction': 8, 'home_latitude': 49., 'home_longitude': 8.,
           'battery': {'remain_flight_time': 900, 'return_home_power': 25, 'landing_power': 10,
                       'batteries': [{'index': 0, 'sn': 'secret-sn', 'loop_times': 42,
                                      'voltage': 16000, 'temperature': 30}]},
           'position_state': {'quality': 10}, 'storage': {'total': 1000, 'used': 200},
           'obstacle_avoidance': {'horizon': 1, 'upside': 0, 'downside': 1},
           'dongle_infos': [{'imei': 'private-imei', 'sim_info': {'iccid': 'private-iccid'}}],
           'device_secret': 'secret-token'}
    d = normalize_details('aircraft', raw)
    assert d['wind_speed_mps'] == pytest.approx(12.3)
    assert d['battery']['remaining_flight_time_s'] == 900
    assert d['battery_packs'][0]['cycle_count'] == 42
    assert d['obstacle_avoidance']['horizon_enabled'] is True
    assert d['position']['quality_code'] == 10
    # Canonical validation must not apply wire wind conversion a second time.
    snap = parse_snapshot(CLOUD, {'device_id': DRONE, 'cloud_details': d})
    assert snap.cloud_details['wind_speed_mps'] == pytest.approx(12.3)
    serialized = json.dumps(asdict(snap))
    assert all(secret not in serialized for secret in ('secret-sn', 'private-imei', 'private-iccid', 'secret-token'))


@pytest.mark.parametrize('raw', [
    {'wind_speed': -1}, {'attitude_roll': float('nan')},
    {'battery': {'batteries': [{}]*9}}, {'89-0-0': {'gimbal_pitch': 500}},
    {'storage': {'used': 1.5}}, {'obstacle_avoidance': {'horizon': 2}},
    {'maintain_status': {'maintain_status_array': [{}]*17}},
])
def test_invalid_extended_properties_are_rejected(raw):
    with pytest.raises(ValueError):
        normalize_osd(DeviceType.AIRCRAFT, raw)


@pytest.mark.parametrize('raw', [{'secret': 'x'}, {'payloads': {'../../x': {}}},
                                 {'battery_packs': [{'sn': 'x'}]}])
def test_canonical_parser_rejects_unapproved_fields(raw):
    with pytest.raises(ValueError):
        validate_details(raw)


@pytest.mark.parametrize('timestamp', [True, -1, 1.5, '123', float('inf')])
def test_malformed_source_timestamps_rejected(timestamp):
    with pytest.raises(ValueError):
        osd_envelope(json.dumps({'timestamp': timestamp, 'data': {'mode_code': 3}}).encode())


def test_status_api_exposes_per_field_age_and_preserves_bearer_protection(feed, monkeypatch):
    app = importlib.import_module('aeronexus.app').app
    token = 'cloud-api-test-token-' + 'x'*32
    monkeypatch.setenv('AERONEXUS_STATUS_TOKEN', token)
    monkeypatch.setattr(app.state, 'status_runtime', feed[0].runtime)
    push(feed, {'mode_code': 3, 'wind_speed': 100})
    client = TestClient(app)
    assert client.get('/api/v1/status/devices').status_code == 401
    response = client.get('/api/v1/status/devices', headers={'Authorization': 'Bearer '+token})
    assert response.status_code == 200
    v = response.json()['devices'][0]
    assert 'field_status' in v and 'last_known_telemetry' in v
    assert v['last_known_telemetry']['cloud_details']['wind_speed_mps'] == 10
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('model,index', [('M3E', '66-0-0'), ('M3T', '67-0-0'),
                                       ('M3M', '68-0-0'), ('M3TA', '129-0-0'),
                                       ('M4E', '88-0-0'), ('M4T', '89-0-0')])
def test_model_family_uses_documented_payload_index_with_shared_telemetry(feed, model, index):
    assert push(feed, {'cameras': [{'payload_index': index, 'camera_mode': 0,
                                   'remain_photo_num': 1200}],
                       index: {'gimbal_pitch': -90, 'gimbal_roll': 0, 'gimbal_yaw': 30}})
    v = view(feed)
    assert v['name'] == model
    d = v['telemetry']['cloud_details']
    assert d['aircraft_model_hint'] == model and d['cameras'][0]['payload_index'] == index
    assert d['payloads'][index]['gimbal_pitch_deg'] == -90
    feed[1][0] += timedelta(seconds=1)
    assert push(feed, {'mode_code': 3, 'battery': {'capacity_percent': 70},
                       'position_state': {'gps_number': 21, 'quality': 10}})
    v = view(feed)
    assert v['telemetry']['battery_percent'] == 70 and v['name'] == model
    assert 'ir_metering_point' not in d['cameras'][0]  # no fabricated capability/value


@pytest.mark.parametrize('index', ['67-0-0', '129-0-0'])
def test_m3_thermal_metering_and_exposure_are_allowlisted(feed, index):
    assert push(feed, {'cameras': [{
        'payload_index': index, 'ir_metering_mode': 2,
        'ir_metering_point': {'x': .5, 'y': .4, 'temperature': -5},
        'ir_metering_area': {'x': .1, 'y': .2, 'width': .3, 'height': .4,
                             'aver_temperature': 25,
                             'min_temperature_point': {'x': .2, 'y': .3, 'temperature': 20},
                             'max_temperature_point': {'x': .3, 'y': .4, 'temperature': 30}},
        'wide_iso': 5, 'zoom_exposure_mode': 1, 'photo_storage_settings': ['wide', 'ir'],
        'secret': 'must-not-leak'}]})
    d = view(feed)['telemetry']['cloud_details']
    c = d['cameras'][0]
    assert c['ir_metering_point']['temperature_c'] == -5
    assert c['ir_metering_area']['mean_temperature_c'] == 25
    assert c['ir_metering_area']['max_temperature_point']['temperature_c'] == 30
    assert c['wide_iso_code'] == 5 and c['photo_storage_settings'] == ['wide', 'ir']
    assert validate_details(d) == d
    assert 'must-not-leak' not in json.dumps(d)


def test_m3_rc_pro_properties_do_not_require_a_specific_rc_model(feed):
    assert push(feed, {'capacity_percent': 80, 'height': 150,
                       'wireless_link': {'sdr_quality': 4, 'sdr_link_state': 1},
                       'live_capacity': {'available_video_number': 2, 'coexist_video_number_max': 1,
                                         'device_list': [{'sn': 'must-not-leak'}]}}, device=RC)
    d = view(feed, RC)['telemetry']['cloud_details']
    assert d['live_capacity']['available_videos'] == 2
    assert d['wireless_link']['sdr_link_state_code'] == 1
    assert 'must-not-leak' not in json.dumps(d)


def test_unknown_payload_does_not_invent_model_or_temperature(feed):
    assert push(feed, {'mode_code': 3, '999-0-0': {'gimbal_yaw': 12}})
    d = view(feed)['telemetry']['cloud_details']
    assert d['payloads']['999-0-0']['gimbal_yaw_deg'] == 12
    assert 'aircraft_model_hint' not in d and view(feed)['name'] == 'Aircraft'


def test_conflicting_payload_identity_rejects_packet_atomically(feed):
    assert not push(feed, {'mode_code': 3, '66-0-0': {'payload_index': '67-0-0', 'gimbal_yaw': 2}})
    assert not feed[0].runtime.inventory.devices()


@pytest.mark.parametrize('camera', [
    {'payload_index': '../secret'}, {'ir_metering_point': {'x': 2}},
    {'ir_metering_area': {'max_temperature_point': {'temperature': float('nan')}}},
    {'photo_storage_settings': ['secret']}, {'wide_iso': 10**500},
])
def test_invalid_m3_camera_properties_rejected(camera):
    with pytest.raises(ValueError):
        normalize_osd(DeviceType.AIRCRAFT, {'cameras': [camera]})


def test_rc_plus2_drc_and_auth_without_sensitive_permission_values(feed):
    assert push(feed, {'capacity_percent': 80, 'drc_state': 2,
                       'cloud_control_auth': ['flight', 'payload'],
                       'wireless_link': {'sdr_quality': 65535, '4g_quality': 4,
                                         '4g_uav_quality': 0, '4g_gnd_quality': 65535}},
                device=RC)
    details = view(feed, RC)['telemetry']['cloud_details']
    assert details['drc_link_state_code'] == 2
    assert details['cloud_control_authorization_count'] == 2
    assert details['wireless_link'] == {'sdr_quality': None, 'cellular_quality': 4,
                                        'cellular_aircraft_quality': 0,
                                        'cellular_ground_quality': None}
    assert 'flight' not in json.dumps(details) and 'payload' not in json.dumps(details)
    assert validate_details(details) == details


def test_rc_state_permissions_only_update_on_state_and_do_not_refresh_osd(feed):
    assert push(feed, {'capacity_percent': 61}, device=RC)
    feed[1][0] += timedelta(minutes=10)
    assert push(feed, {'drc_state': 1, 'cloud_control_auth': ['flight']},
                device=RC, channel='state')
    v = view(feed, RC)
    assert v['freshness'] == 'stale' and v['online'] is None
    assert v['telemetry']['battery_percent'] is None
    assert v['telemetry']['cloud_details']['drc_link_state_code'] == 1
    assert v['field_status']['cloud_details.drc_link_state_code']['channel'] == 'state'


@pytest.mark.parametrize('payload', [
    {'drc_state': 3}, {'drc_state': -1}, {'cloud_control_auth': 'flight'},
    {'cloud_control_auth': ['x'] * 17}, {'cloud_control_auth': [3]},
    {'wireless_link': {'sdr_quality': 6}},
    {'wireless_link': {'4g_uav_quality': -1}},
])
def test_invalid_rc_extended_telemetry_rejected(payload):
    with pytest.raises(ValueError):
        normalize_osd(DeviceType.CONTROLLER, payload)


@pytest.mark.parametrize('source,expected', [
    ('A', 'controller_a'), ('B', 'controller_b'), ('', 'unassigned'),
    ('00000000-0000-4000-8000-000000000123', 'browser'),
    ('some_unknown_device_name', 'other'),
])
def test_aircraft_control_source_is_category_only(source, expected):
    raw = {'mode_code': 3, 'control_source': source,
           'payloads': [{'payload_index': '89-0-0', 'control_source': source,
                         'sn': 'SENSITIVE-PAYLOAD-SERIAL'}]}
    details = normalize_osd(DeviceType.AIRCRAFT, raw)['cloud_details']
    assert details['control_source_category'] == expected
    assert details['payload_control'][0]['control_source_category'] == expected
    assert 'SENSITIVE' not in json.dumps(details)
    assert source not in json.dumps(details) if expected == 'browser' else True
    assert validate_details(details) == details


def test_invalid_control_source_and_payload_control_fail_closed():
    for raw in ({'control_source': 42}, {'control_source': 'A\\nsecret'},
                {'payloads': [{'payload_index': '../bad'}]},
                {'payloads': [{'control_source': 23}]}):
        with pytest.raises(ValueError):
            normalize_osd(DeviceType.AIRCRAFT, {'mode_code': 3, **raw})
