"""Reject mixed catalogue snapshots in individual image and stack exports."""
import importlib

import pytest

from aeronexus.minio_media_index import DjiMediaChanged
from test_multispectral import UUID, api, ms  # noqa: F401
from test_thermal import HEADERS


def replace_nir(ms, *, scan_catalog=False):
    key = 'wayline/org_a_1.tiff'
    data, etag = ms.client.items[key]
    ms.client.items[key] = (data, etag + '-changed')
    ms.media.scan(ms.client, 'dji-cloud')
    if scan_catalog:
        ms.catalog.scan(ms.client, 'dji-cloud')


@pytest.mark.parametrize('cached', [False, True])
def test_single_image_rejects_media_index_ahead_of_catalog(ms, cached):
    ms.catalog.scan(ms.client, 'dji-cloud')
    if cached:
        ms.analysis(UUID, 'ndvi', scale=4)
    replace_nir(ms)
    with pytest.raises(DjiMediaChanged):
        ms.analysis(UUID, 'ndvi', scale=4)
    ms.catalog.scan(ms.client, 'dji-cloud')
    assert ms.analysis(UUID, 'ndvi', scale=4)['stats']['median'] is not None


@pytest.mark.parametrize('scan_catalog', [False, True])
def test_layer_discards_source_changes_during_calculation(ms, monkeypatch, scan_catalog):
    module = importlib.import_module('aeronexus.multispectral')
    ms.catalog.scan(ms.client, 'dji-cloud')
    original = module.compute_layer

    def compute(*args, **kwargs):
        grid = original(*args, **kwargs)
        replace_nir(ms, scan_catalog=scan_catalog)
        return grid

    monkeypatch.setattr(module, 'compute_layer', compute)
    with pytest.raises(DjiMediaChanged):
        ms.layer(UUID, 'ndvi', scale=4)


def test_analysis_does_not_store_summary_if_source_changes_during_statistics(ms, monkeypatch):
    module = importlib.import_module('aeronexus.multispectral')
    ms.catalog.scan(ms.client, 'dji-cloud')
    original = module.layer_stats

    def statistics(*args, **kwargs):
        result = original(*args, **kwargs)
        replace_nir(ms)
        return result

    monkeypatch.setattr(module, 'layer_stats', statistics)
    with pytest.raises(DjiMediaChanged):
        ms.analysis(UUID, 'ndvi', scale=4)
    assert ms.catalog.summaries() == {}


def test_assert_current_rejects_old_catalogue_even_after_media_returns_to_old_etag(ms):
    ms.catalog.scan(ms.client, 'dji-cloud')
    capture = ms.catalog.capture(UUID)
    key = 'wayline/org_a_1.tiff'
    original = ms.client.items[key]
    replace_nir(ms, scan_catalog=True)
    ms.client.items[key] = original
    ms.media.scan(ms.client, 'dji-cloud')
    with pytest.raises(DjiMediaChanged):
        ms.catalog.assert_current(capture)


def test_stack_rejects_outdated_catalog_before_reading_originals(ms):
    ms.catalog.scan(ms.client, 'dji-cloud')
    replace_nir(ms)
    before = ms.client.gets
    with pytest.raises(DjiMediaChanged):
        ms.stack_geotiff(UUID, scale=2, refine=False)
    assert ms.client.gets == before


def test_stack_discards_source_changes_during_encoding(ms, monkeypatch):
    module = importlib.import_module('aeronexus.m3m_stack')
    ms.catalog.scan(ms.client, 'dji-cloud')
    original = module.stack_to_geotiff

    def encode(*args, **kwargs):
        result = original(*args, **kwargs)
        replace_nir(ms, scan_catalog=True)
        return result

    monkeypatch.setattr(module, 'stack_to_geotiff', encode)
    with pytest.raises(DjiMediaChanged):
        ms.stack_geotiff(UUID, scale=2, refine=False)
    assert ms._compute.acquire(timeout=.1)  # rejected export releases shared slot
    ms._compute.release()


@pytest.mark.parametrize('path', ['layers/ndvi?scale=4', 'layers/ndvi/grid?scale=4',
                                  'stack.tif?scale=2&refine=false'])
def test_individual_api_returns_conflict_for_outdated_catalog(api, ms, path):
    replace_nir(ms)
    response = api.get(f'/api/v1/multispectral/captures/{UUID}/{path}', headers=HEADERS)
    assert response.status_code == 409
    assert 'reindex' in response.json()['detail']
