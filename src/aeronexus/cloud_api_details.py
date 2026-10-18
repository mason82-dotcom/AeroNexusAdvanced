"""Allowlisted Cloud API 1.18 properties; no raw payload or hardware identifiers.

M4 / RC Plus 2 property tables, retrieved 2026-10-17. DRC, HMS, topology,
camera control and SIM/battery serial numbers are outside this decoder.
"""
from collections.abc import Mapping
from math import isfinite
import re


PAYLOAD_INDEX = re.compile(r"[0-9]{1,5}-[0-9]{1,3}-[0-9]{1,3}\Z")
PAYLOAD_MODELS = {'66-0-0': 'M3E', '67-0-0': 'M3T', '68-0-0': 'M3M',
                  '129-0-0': 'M3TA', '88-0-0': 'M4E', '89-0-0': 'M4T'}


def number(low=None, high=None, *, integer=False, factor=1):
    def parse(value):
        if value is None:
            return None
        if isinstance(value, str) and 0 < len(value) <= 32:
            try:
                value = float(value)
            except ValueError:
                raise ValueError("Invalid Cloud API number") from None
        try:
            finite = type(value) in (int, float) and isfinite(value)
        except (OverflowError, TypeError):
            finite = False
        if not finite:
            raise ValueError("Invalid Cloud API number")
        if (low is not None and value < low) or (high is not None and value > high):
            raise ValueError("Cloud API number outside bounds")
        if integer and int(value) != value:
            raise ValueError("Cloud API integer required")
        return int(value) if integer else value * factor
    return parse


def text(value):
    if value is None:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= 64 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid Cloud API text")
    return value


def switch(value):
    if value is None or type(value) is bool:
        return value
    if type(value) is int and value in (0, 1):
        return bool(value)
    raise ValueError("Invalid Cloud API switch")


def payload_index(value):
    if not isinstance(value, str) or not PAYLOAD_INDEX.fullmatch(value):
        raise ValueError("Invalid payload index")
    return value


def model_hint(value):
    if value not in PAYLOAD_MODELS.values():
        raise ValueError("Invalid aircraft model hint")
    return value


COUNT = number(0, 2**53 - 1, integer=True)
CODE = number(0, 2**31 - 1, integer=True)
PERCENT = number(0, 100)
ANGLE = number(-360, 360)
DRC_STATE = number(0, 2, integer=True)
LINK_QUALITY = number(0, 5, integer=True)


def link_quality(value):
    """DJI uses 65535 as unavailable in some RC wire examples; never show 65535/5."""
    if value == 65535 or value == '65535':
        return None
    return LINK_QUALITY(value)


_SOURCE_CATEGORIES = frozenset({'unassigned', 'controller_a', 'controller_b',
                                'browser', 'other'})
_UUID = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')


def control_source_category(value):
    """Report control authority kind without ever retaining browser UUIDs."""
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 64 or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid control source')
    if value in _SOURCE_CATEGORIES:  # canonical validation is idempotent
        return value
    if value == '':
        return 'unassigned'
    if value == 'A':
        return 'controller_a'
    if value == 'B':
        return 'controller_b'
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', value):
        raise ValueError('Invalid control source syntax')
    return 'browser' if _UUID.fullmatch(value) else 'other'


def authorization_count_wire(value):
    """Validate DJI list but expose only its size, never arbitrary strings."""
    if not isinstance(value, list) or len(value) > 16:
        raise ValueError('Invalid cloud authorization list')
    if any(not isinstance(item, str) or not 1 <= len(item) <= 64
           or any(ord(c) < 32 for c in item) for item in value):
        raise ValueError('Invalid cloud authorization entry')
    return len(value)


def authorization_count(value):
    """Validate normalized telemetry without accepting numbers on DJI wire."""
    if type(value) is not int or not 0 <= value <= 16:
        raise ValueError('Invalid canonical authorization count')
    return value

# wire key: (canonical key, parser). Unknown enums are retained as numeric
# codes, never guessed into labels. Wind's wire unit is 0.1 m/s, not m/s.
AIRCRAFT = {
    'control_source': ('control_source_category', control_source_category),
    'attitude_head': ('heading_deg', ANGLE),
    'attitude_roll': ('roll_deg', ANGLE),
    'attitude_pitch': ('pitch_deg', ANGLE),
    'wind_speed': ('wind_speed_mps', number(0, factor=.1)),
    'wind_direction': ('wind_direction_code', CODE),
    'home_latitude': ('home_latitude', number(-90, 90)),
    'home_longitude': ('home_longitude', number(-180, 180)),
    'total_flight_distance': ('total_flight_distance_m', number(0)),
    'height_limit': ('height_limit_m', number(0)),
    'is_near_area_limit': ('near_area_limit', switch),
    'is_near_height_limit': ('near_height_limit', switch),
    'night_lights_state': ('night_lights_on', switch),
    'low_battery_warning_threshold': ('low_battery_warning_percent', PERCENT),
    'serious_low_battery_warning_threshold': ('critical_battery_warning_percent', PERCENT),
    'mode_code_reason': ('flight_mode_reason_code', CODE),
    'gear': ('gear_code', CODE),
    'current_rth_mode': ('current_rth_mode_code', CODE),
    'rth_mode': ('rth_mode_code', CODE),
    'activation_time': ('activation_time_s', COUNT),
    'firmware_upgrade_status': ('firmware_upgrade_status_code', CODE),
    'compatible_status': ('firmware_compatible_status_code', CODE),
    # DJI Pilot-to-Cloud aircraft properties: read-only projection, including
    # writable-on-device settings observed on OSD/state. Never publish changes.
    'wpmz_version': ('wayline_library_version', text),
    'rth_altitude': ('return_home_altitude_m', number(0, 3000)),
    'rc_lost_action': ('rc_signal_lost_action_code', number(0, 2, integer=True)),
    'exit_wayline_when_rc_lost': ('wayline_rc_lost_action_code', number(0, 1, integer=True)),
    'rid_state': ('remote_id_ok', switch),
    'commander_mode_lost_action': ('commander_lost_action_code', number(0, 1, integer=True)),
    'current_commander_flight_mode': ('commander_flight_mode_code', number(0, 1, integer=True)),
    'commander_flight_height': ('commander_flight_height_m', number(0, 3000)),
}
COMMON = {'firmware_version': ('firmware_version', text)}
BATTERY = {
    'remain_flight_time': ('remaining_flight_time_s', COUNT),
    'return_home_power': ('return_home_battery_percent', PERCENT),
    'landing_power': ('landing_battery_percent', PERCENT),
}
PACK = {
    'index': ('index', COUNT), 'capacity_percent': ('capacity_percent', PERCENT),
    'voltage': ('voltage_mv', number(0)), 'temperature': ('temperature_c', number()),
    'loop_times': ('cycle_count', COUNT), 'high_voltage_storage_days': ('high_voltage_storage_days', COUNT),
    'type': ('type_code', CODE), 'sub_type': ('subtype_code', CODE),
    'firmware_version': ('firmware_version', text),
}
DISTANCE_LIMIT = {
    'state': ('configured_code', number(0, 1, integer=True)),
    'distance_limit': ('distance_limit_m', number(0, 8000)),
    'is_near_distance_limit': ('near_distance_limit', switch),
}
# Identifiers (IMEI, EID, ICCID, phone/SIM tokens) are never copied.
SIM_INFO = {
    'telecom_operator': ('operator_code', number(0, 3, integer=True)),
    'sim_type': ('sim_type_code', number(0, 2, integer=True)),
}
ESIM_INFO = {
    'telecom_operator': ('operator_code', number(0, 3, integer=True)),
    'enabled': ('enabled', switch),
}
DONGLE = {
    'dongle_type': ('type_code', CODE),
    'esim_activate_state': ('esim_activation_code', CODE),
    'sim_card_state': ('sim_card_state_code', number(0, 1, integer=True)),
    'sim_slot': ('sim_slot_code', number(0, 2, integer=True)),
}
RC = {
    'height': ('controller_height_m', number()),
    'drc_state': ('drc_link_state_code', DRC_STATE),
    'cloud_control_auth': ('cloud_control_authorization_count', authorization_count_wire),
}
WIRELESS = {
    'dongle_number': ('dongle_count', COUNT),
    '4g_link_state': ('cellular_link_state_code', CODE),
    'sdr_link_state': ('sdr_link_state_code', CODE),
    'link_workmode': ('link_workmode_code', CODE),
    'sdr_quality': ('sdr_quality', link_quality), '4g_quality': ('cellular_quality', link_quality),
    '4g_uav_quality': ('cellular_aircraft_quality', link_quality),
    '4g_gnd_quality': ('cellular_ground_quality', link_quality),
    'sdr_freq_band': ('sdr_frequency_ghz', number(0, 100)),
    '4g_freq_band': ('cellular_frequency_ghz', number(0, 100)),
}
PAYLOAD = {
    'gimbal_pitch': ('gimbal_pitch_deg', ANGLE), 'gimbal_roll': ('gimbal_roll_deg', ANGLE),
    'gimbal_yaw': ('gimbal_yaw_deg', ANGLE), 'zoom_factor': ('zoom_factor', number(0, 1000)),
}
PAYLOAD_CONTROL = {
    'payload_index': ('payload_index', payload_index),
    'control_source': ('control_source_category', control_source_category),
    'firmware_version': ('firmware_version', text),
}
CAMERA = {
    **PAYLOAD, 'payload_index': ('payload_index', payload_index),
    'camera_mode': ('camera_mode_code', CODE), 'photo_state': ('photo_state_code', CODE),
    'recording_state': ('recording_state_code', CODE), 'record_time': ('record_time_s', COUNT),
    'remain_photo_num': ('remaining_photos', COUNT),
    'remain_record_duration': ('remaining_record_time_s', COUNT),
    'ir_zoom_factor': ('ir_zoom_factor', number(0, 1000)),
    'screen_split_enable': ('split_screen_enabled', switch),
    'ir_metering_mode': ('ir_metering_mode_code', CODE),
}
for lens in ('wide', 'zoom'):
    for setting in ('exposure_mode', 'iso', 'shutter_speed', 'exposure_value', 'focus_mode',
                    'focus_state', 'focus_value', 'max_focus_value', 'min_focus_value',
                    'calibrate_farthest_focus_value', 'calibrate_nearest_focus_value'):
        CAMERA[f'{lens}_{setting}'] = (f'{lens}_{setting}_code' if setting in (
            'exposure_mode', 'iso', 'shutter_speed', 'exposure_value', 'focus_mode', 'focus_state')
            else f'{lens}_{setting}', CODE)
METER_POINT = {'x': ('x', number(0, 1)), 'y': ('y', number(0, 1)),
               'temperature': ('temperature_c', number(-273.15, 5000))}
METER_AREA = {k: (k, number(0, 1)) for k in ('x', 'y', 'width', 'height')}
METER_AREA['aver_temperature'] = ('mean_temperature_c', number(-273.15, 5000))
LIVE = {
    'video_type': ('video_type', text), 'video_quality': ('quality_code', CODE),
    'status': ('status_code', CODE), 'error_status': ('error_code', CODE),
}
CAPACITY = {
    'available_video_number': ('available_videos', COUNT),
    'coexist_video_number_max': ('simultaneous_videos', COUNT),
}
STORAGE = {'total': ('total_kib', COUNT), 'used': ('used_kib', COUNT)}
OBSTACLES = {k: (k + '_enabled', switch) for k in ('horizon', 'upside', 'downside')}
# DJI M3 uses wide/zoom, while M4 (e.g. RC Plus 2/M4T) uses vision.
# Accept both documented wire enum families, never arbitrary storage values.
STORAGE_TYPES = frozenset(('current', 'wide', 'zoom', 'ir', 'vision'))
MAINTENANCE = {
    'state': ('state_code', CODE), 'last_maintain_type': ('last_type_code', CODE),
    'last_maintain_time': ('last_time_s', COUNT),
    'last_maintain_flight_time': ('last_flight_hours', number(0)),
    'last_maintain_flight_sorties': ('last_sorties', COUNT),
}


def mapped(data, schema):
    if not isinstance(data, Mapping):
        raise ValueError("Invalid Cloud API property object")
    return {name: parse(data[key]) for key, (name, parse) in schema.items() if key in data}


def array(data, schema, limit):
    if not isinstance(data, list) or len(data) > limit:
        raise ValueError("Invalid Cloud API property array")
    return [mapped(row, schema) for row in data]


def camera(data):
    result = mapped(data, CAMERA)
    for key, schema in [('ir_metering_point', METER_POINT), ('liveview_world_region',
                        {k: (k, number(0, 1)) for k in ('left', 'top', 'right', 'bottom')})]:
        if key in data and data[key] is not None:
            result[key] = mapped(data[key], schema)
    if 'ir_metering_area' in data and data['ir_metering_area'] is not None:
        area = data['ir_metering_area']
        result['ir_metering_area'] = mapped(area, METER_AREA)
        for key in ('min_temperature_point', 'max_temperature_point'):
            if key in area and area[key] is not None:
                result['ir_metering_area'][key] = mapped(area[key], METER_POINT)
    for key in ('photo_storage_settings', 'video_storage_settings'):
        if key in data:
            values = data[key]
            if not isinstance(values, list) or len(values) > 4 or any(v not in STORAGE_TYPES for v in values):
                raise ValueError("Invalid camera storage settings")
            result[key] = list(values)
    return result


def dongles(data):
    """Copy only categorical cellular state; omit all unique SIM/hardware IDs."""
    items = array(data, DONGLE, 8)
    for row, source in zip(items, data):
        if 'sim_info' in source and source['sim_info'] is not None:
            info = mapped(source['sim_info'], SIM_INFO)
            if info:
                row['sim_info'] = info
        if 'esim_infos' in source and source['esim_infos'] is not None:
            row['esim_infos'] = array(source['esim_infos'], ESIM_INFO, 8)
    return items


def normalize_details(kind, data):
    aircraft = kind == 'aircraft'
    result = mapped(data, COMMON | (AIRCRAFT if aircraft else RC))
    if aircraft:
        for wire, target, schema in [('distance_limit_status', 'distance_limit', DISTANCE_LIMIT),
                                     ('battery', 'battery', BATTERY),
                                     ('position_state', 'position', {'quality': ('quality_code', CODE)}),
                                     ('storage', 'storage', STORAGE),
                                     ('obstacle_avoidance', 'obstacle_avoidance', OBSTACLES)]:
            if wire in data and data[wire] is not None:
                value = mapped(data[wire], schema)
                if value:
                    result[target] = value
        battery = data.get('battery') or {}
        if 'batteries' in battery:
            result['battery_packs'] = array(battery['batteries'], PACK, 8)
        maintenance = data.get('maintain_status')
        if maintenance is not None:
            if not isinstance(maintenance, Mapping):
                raise ValueError("Invalid maintenance object")
            if 'maintain_status_array' in maintenance:
                result['maintenance'] = array(maintenance['maintain_status_array'], MAINTENANCE, 16)
        payloads = {}
        for key, value in data.items():
            if PAYLOAD_INDEX.fullmatch(key):
                if isinstance(value, Mapping) and 'payload_index' in value and value['payload_index'] != key:
                    raise ValueError("Conflicting payload index")
                parsed = mapped(value, PAYLOAD)
                if parsed:
                    payloads[key] = parsed
        if len(payloads) > 16:
            raise ValueError("Too many Cloud API payloads")
        if payloads:
            result['payloads'] = payloads
        if 'payloads' in data:
            payload_control = array(data['payloads'], PAYLOAD_CONTROL, 16)
            # Ignore legacy/unknown-only payload objects, but never register
            # a partial control record without the documented payload index.
            if any('payload_index' not in item for item in payload_control):
                if any(item for item in payload_control):
                    raise ValueError('Payload control missing payload index')
            else:
                result['payload_control'] = payload_control
        if 'dongle_infos' in data:
            result['dongles'] = dongles(data['dongle_infos'])
        if 'cameras' in data:
            cameras = data['cameras']
            if not isinstance(cameras, list) or len(cameras) > 16:
                raise ValueError("Invalid camera array")
            result['cameras'] = [camera(row) for row in cameras]
        indexes = (list(payloads) + [row.get('payload_index') for row in result.get('cameras', [])]
                   + [row.get('payload_index') for row in result.get('payload_control', [])])
        models = {PAYLOAD_MODELS[index] for index in indexes if index in PAYLOAD_MODELS}
        if len(models) == 1:
            result['aircraft_model_hint'] = models.pop()
    else:
        if 'dongle_infos' in data:
            result['dongles'] = dongles(data['dongle_infos'])
        for wire, schema in [('wireless_link', WIRELESS), ('live_capacity', CAPACITY)]:
            if wire in data and data[wire] is not None:
                parsed = mapped(data[wire], schema)
                if parsed:
                    result[wire] = parsed
        if 'live_status' in data:
            result['live_status'] = array(data['live_status'], LIVE, 16)
    # A half home coordinate pair and DJI's unknown 0/0 do not locate a home.
    if 'home_latitude' in result or 'home_longitude' in result:
        lat, lon = result.get('home_latitude'), result.get('home_longitude')
        if lat is None or lon is None or (lat == 0 and lon == 0):
            result['home_latitude'] = result['home_longitude'] = None
    return result


def canonical_schema(mapping):
    return {name: parse for name, parse in mapping.values()}


DETAILS_SCHEMA = canonical_schema(COMMON | AIRCRAFT | RC) | {
 'battery': canonical_schema(BATTERY),
    'position': {'quality_code': CODE}, 'storage': canonical_schema(STORAGE),
    'distance_limit': canonical_schema(DISTANCE_LIMIT),
    'dongles': (canonical_schema(DONGLE) | {
        'sim_info': canonical_schema(SIM_INFO),
        'esim_infos': (canonical_schema(ESIM_INFO), 8)}, 8),
    'obstacle_avoidance': canonical_schema(OBSTACLES), 'battery_packs': (canonical_schema(PACK), 8),
    'maintenance': (canonical_schema(MAINTENANCE), 16), 'payloads': ('payloads', canonical_schema(PAYLOAD)),
    'payload_control': (canonical_schema(PAYLOAD_CONTROL), 16),
    'cameras': (canonical_schema(CAMERA) | {
        'ir_metering_point': canonical_schema(METER_POINT),
        'ir_metering_area': canonical_schema(METER_AREA) | {
            key: canonical_schema(METER_POINT) for key in ('min_temperature_point', 'max_temperature_point')},
        'liveview_world_region': {k: number(0, 1) for k in ('left', 'top', 'right', 'bottom')},
        'photo_storage_settings': ('storage_settings', 4), 'video_storage_settings': ('storage_settings', 4),
    }, 16), 'wireless_link': canonical_schema(WIRELESS),
    'live_status': (canonical_schema(LIVE), 16), 'live_capacity': canonical_schema(CAPACITY),
    'aircraft_model_hint': model_hint,
}
# Canonical wind is already in m/s. Never apply the wire conversion twice.
DETAILS_SCHEMA['wind_speed_mps'] = number(0)
DETAILS_SCHEMA['cloud_control_authorization_count'] = authorization_count


def validate_details(data, schema=DETAILS_SCHEMA):
    if data is None:
        return None
    if not isinstance(data, Mapping) or set(data) - set(schema):
        raise ValueError("Invalid canonical Cloud API properties")
    result = {}
    for key, value in data.items():
        rule = schema[key]
        if isinstance(rule, dict):
            result[key] = validate_details(value, rule)
        elif isinstance(rule, tuple):
            child, limit = rule
            if child == 'storage_settings':
                if not isinstance(value, list) or len(value) > limit or any(v not in STORAGE_TYPES for v in value):
                    raise ValueError("Invalid canonical storage settings")
                result[key] = list(value)
            elif child == 'payloads':
                if not isinstance(value, Mapping) or len(value) > 16 or any(not PAYLOAD_INDEX.fullmatch(k) for k in value):
                    raise ValueError("Invalid canonical payloads")
                result[key] = {k: validate_details(v, limit) for k, v in value.items()}
            else:
                if not isinstance(value, list) or len(value) > limit:
                    raise ValueError("Invalid canonical property array")
                result[key] = [validate_details(v, child) for v in value]
        else:
            result[key] = rule(value)
    return result
