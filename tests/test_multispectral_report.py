"""Series reports: exact masks, partial failures, source races and access control."""
import csv
import io
import json
from types import SimpleNamespace

import numpy as np
import pytest

from aeronexus.minio_media_index import DjiMediaChanged
from aeronexus.multispectral import MultispectralError
from aeronexus.multispectral_report import build_report, report_csv, summarize
from test_multispectral import HEADERS, SERIAL, UUID, api, ms


def test_mask_uses_joint_finite_pixels_and_keeps_input_untouched():
    grid = np.array([[1., 2., np.nan], [4., 5., 6.]], np.float32)
    ndvi = np.array([[.2, .1, .9], [.8, np.nan, .9]], np.float32)
    stats, hist = summarize(grid, ndvi, threshold=.2)
    assert stats['pixels'] == 6 and stats['valid_pixels'] == 5
    assert stats['selected_pixels'] == 3 and stats['selected_share'] == .6
    assert stats['mean'] == pytest.approx(11/3)
    assert stats['std'] == pytest.approx(np.std([1., 4., 6.]))
    assert stats['p10'] == pytest.approx(1.6)
    assert sum(hist['counts']) == 3 and len(hist['edges']) == 33
    assert grid[0, 1] == 2 and np.isnan(grid[0, 2])


@pytest.mark.parametrize('grid,ndvi', [(np.full((2,2), np.nan), None),
                                     (np.ones((2,2)), np.zeros((2,2)))])
def test_empty_statistics_are_null_and_json_serializable(grid, ndvi):
    stats, hist = summarize(grid, ndvi, threshold=.2 if ndvi is not None else None)
    assert stats['selected_pixels'] == 0
    assert stats['mean'] is stats['median'] is stats['std'] is None
    assert hist == {'edges': [], 'counts': []}
    json.dumps(stats, allow_nan=False)


def test_histogram_does_not_clip_lci_and_counts_constant_arrays():
    stats, hist = summarize(np.array([[-3.5, -2., .3, 8.]], np.float32))
    assert stats['min'] == -3.5 and stats['max'] == 8
    assert hist['edges'][0] == -3.5 and hist['edges'][-1] == 8
    assert sum(hist['counts']) == 4
    stats, hist = summarize(np.full((4,4), .5, np.float32))
    assert stats['std'] == 0 and sum(hist['counts']) == 16


def test_report_uses_real_calibration_and_csv_preserves_settings(ms):
    ms.catalog.scan(ms.client, 'dji-cloud')
    expected = ms.analysis(UUID, 'ndvi', scale=4)['stats']['mean']
    report = build_report(ms, [UUID], ['ndvi', 'ndre'], threshold=.2)
    assert len(report['rows']) == 2 and all(r['status'] == 'ok' for r in report['rows'])
    assert report['rows'][0]['stats']['mean'] == pytest.approx(expected, abs=1e-5)
    assert report['rows'][0]['stats']['selected_pixels'] > 0
    assert SERIAL not in repr(report) and 'source_key' not in repr(report)
    assert 'object_key' not in repr(report)
    table = list(csv.DictReader(io.StringIO(report_csv(report).lstrip('\ufeff')), delimiter=';'))
    assert table[0]['scale'] == '4' and table[0]['ndvi_threshold'] == '0.2'
    assert table[0]['capture_uuid'] == UUID


def test_missing_band_does_not_hide_successful_other_layer(ms):
    del ms.client.items['wayline/org_b_1.tiff']  # Red
    ms.media.scan(ms.client, 'dji-cloud')
    ms.catalog.scan(ms.client, 'dji-cloud')
    result = build_report(ms, [UUID, '0'*32], ['ndvi', 'ndre'])
    assert [r['status'] for r in result['rows']] == ['error', 'ok', 'error', 'error']
    # With an NDVI mask all requested indices need the missing Red band.
    masked = build_report(ms, [UUID], ['ndre'], threshold=.2)
    assert masked['rows'][0]['status'] == 'error'


def test_changed_source_discards_all_rows_for_capture():
    calls = 0
    def layer(uuid, name, scale):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise DjiMediaChanged('private bucket/key')
        return {'source_key': 'a'}, np.ones((2,2))
    service = SimpleNamespace(catalog=SimpleNamespace(capture=lambda _: {'source_key':'a'}, assert_current=lambda _: None), layer=layer)
    result = build_report(service, [UUID], ['ndvi','ndre'])
    assert all(r['code'] == 'source_changed' for r in result['rows'])
    assert 'private' not in json.dumps(result)
    assert all('stats' not in r for r in result['rows'])


def test_changed_catalog_after_last_layer_discards_stale_result():
    count = 0
    def capture(_):
        nonlocal count
        count += 1
        return {'source_key': 'a' if count == 1 else 'b'}
    service = SimpleNamespace(catalog=SimpleNamespace(capture=capture, assert_current=lambda _: None),
                              layer=lambda *a, **k: ({'source_key':'a'}, np.ones((2,2))))
    assert build_report(service, [UUID], ['ndvi'])['rows'][0]['code'] == 'source_changed'


@pytest.mark.parametrize('kwargs', [{'capture_uuids':[UUID, UUID]}, {'layers':['ndvi','ndvi']},
                                    {'threshold':float('nan')}, {'scale':3}])
def test_invalid_batch_parameters(kwargs):
    params = dict(capture_uuids=[UUID], layers=['ndvi']) | kwargs
    with pytest.raises(MultispectralError):
        build_report(None, **params)


def test_api_auth_json_csv_validation_and_busy_slot(api):
    from test_thermal import APP_MODULE
    body = {'capture_uuids':[UUID], 'layers':['ndvi'], 'scale':4, 'ndvi_threshold':.2}
    url = '/api/v1/multispectral/reports'
    assert api.post(url, json=body).status_code == 401
    result = api.post(url, json=body, headers=HEADERS)
    assert result.status_code == 200 and result.json()['rows'][0]['status'] == 'ok'
    assert 'no-store' in result.headers['cache-control']
    result = api.post(url+'?format=csv', json=body, headers=HEADERS)
    assert result.status_code == 200 and result.text.startswith('\ufeffcapture_uuid;')
    assert 'attachment' in result.headers['content-disposition']
    for patch in ({'capture_uuids':[]}, {'capture_uuids':[UUID]*21}, {'layers':['evi']},
                  {'scale':3}, {'ndvi_threshold':2}, {'capture_uuids':['bad']}, {'extra':True}):
        assert api.post(url, json=body | patch, headers=HEADERS).status_code == 422
    assert api.post(url, json=body | {'capture_uuids':[UUID,UUID]}, headers=HEADERS).status_code == 422
    assert APP_MODULE._MS_REPORT_SLOT.acquire(blocking=False)
    try:
        result = api.post(url, json=body, headers=HEADERS)
        assert result.status_code == 429 and result.headers['retry-after'] == '5'
    finally:
        APP_MODULE._MS_REPORT_SLOT.release()
    assert api.post(url, json=body, headers=HEADERS).status_code == 200


def test_csv_quotes_formula_cells():
    report = {'rows':[{'capture_uuid':'x', 'captured_at':' =1+1', 'layer':'ndvi', 'status':'error'}],
              'scale':4, 'ndvi_threshold':None}
    rows = list(csv.DictReader(io.StringIO(report_csv(report).lstrip('\ufeff')), delimiter=';'))
    assert rows[0]['captured_at'] == "' =1+1"


def test_processing_busy_is_distinct_from_invalid_calibration():
    from aeronexus.multispectral import MultispectralBusy
    def layer(*args, **kwargs):
        raise MultispectralBusy('private diagnostic')
    service = SimpleNamespace(catalog=SimpleNamespace(capture=lambda _: {'source_key':'a'}, assert_current=lambda _: None), layer=layer)
    for threshold in (None, .2):
        report = build_report(service, [UUID], ['ndvi'], threshold=threshold)
        assert report['rows'][0]['code'] == 'processing_busy'
        assert 'private' not in json.dumps(report)


def test_report_rejects_media_index_newer_than_catalogue(ms):
    ms.catalog.scan(ms.client, 'dji-cloud')
    key = 'wayline/org_a_1.tiff'
    data, etag = ms.client.items[key]
    ms.client.items[key] = (data, etag + 'changed')
    ms.media.scan(ms.client, 'dji-cloud')  # intentionally not a catalogue scan
    report = build_report(ms, [UUID], ['ndvi', 'ndre'])
    assert all(row['code'] == 'source_changed' for row in report['rows'])
    assert all('stats' not in row for row in report['rows'])
    ms.catalog.scan(ms.client, 'dji-cloud')
    assert all(row['status'] == 'ok' for row in build_report(ms, [UUID], ['ndvi', 'ndre'])['rows'])


def test_report_discards_results_if_media_index_changes_after_raster(ms, monkeypatch):
    ms.catalog.scan(ms.client, 'dji-cloud')
    original = ms.layer
    def layer(*args, **kwargs):
        result = original(*args, **kwargs)
        key = 'wayline/org_a_1.tiff'
        data, etag = ms.client.items[key]
        ms.client.items[key] = (data, etag + 'changed')
        ms.media.scan(ms.client, 'dji-cloud')
        return result
    monkeypatch.setattr(ms, 'layer', layer)
    row, = build_report(ms, [UUID], ['ndvi'])['rows']
    assert row['code'] == 'source_changed' and 'stats' not in row
