"""Raster API exercises the real catalog/rendering and the gateway access policy."""
import importlib

import pytest
from fastapi.testclient import TestClient

from test_raster_results import raster, xyz
from aeronexus.raster_results import RasterResults, RasterUnavailable

APP = importlib.import_module('aeronexus.app')
TOKEN = 'raster-viewer-test-token-12345678901234567890'
HEADERS = {'Authorization': 'Bearer ' + TOKEN}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('AERONEXUS_WORKSPACE_DIR', str(tmp_path / 'workspace'))
    monkeypatch.setenv('AERONEXUS_RESULTS_DIR', str(tmp_path / 'rasters'))
    monkeypatch.setenv('AERONEXUS_STATUS_TOKEN', TOKEN)
    monkeypatch.delenv('AERONEXUS_LAN_NO_TOKEN', raising=False)
    source = tmp_path / 'rasters'
    source.mkdir()
    raster(source / 'test_ndvi.tif')
    return TestClient(APP.app)


def test_catalog_scan_metadata_statistics_and_tiles(client):
    assert client.get('/api/v1/results', headers=HEADERS).json()['total'] == 0
    report = client.post('/api/v1/results/scan', headers=HEADERS)
    assert report.status_code == 200, report.text
    assert report.json()['indexed'] == 1
    result = client.get('/api/v1/results', headers=HEADERS)
    assert result.headers['cache-control'] == 'no-store'
    data = result.json()
    assert data['raster_available'] is True
    item = data['items'][0]
    assert '/rasters/' not in result.text and '/workspace/' not in result.text
    assert client.get('/api/v1/results/'+item['id'], headers=HEADERS).json() == item
    stats = client.get('/api/v1/results/'+item['id']+'/statistics', headers=HEADERS)
    assert stats.status_code == 200 and stats.json()['min'] == 0
    tile = client.get('/api/v1/results/'+item['id']+'/tiles/'+ '/'.join(map(str, xyz()))+'.png', headers=HEADERS)
    assert tile.status_code == 200 and tile.content.startswith(b'\x89PNG')
    assert tile.headers['content-type'] == 'image/png'
    assert tile.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('method,path', [('get',''),('post','/scan'),('get','/bad'),('get','/bad/statistics'),('get','/bad/tiles/0/0/0.png')])
def test_all_data_routes_require_credentials(client, method, path):
    assert getattr(client, method)('/api/v1/results'+path).status_code == 401


def test_validation_missing_and_changed_source(client):
    client.post('/api/v1/results/scan', headers=HEADERS)
    item = client.get('/api/v1/results', headers=HEADERS).json()['items'][0]
    base = '/api/v1/results/' + item['id']
    assert client.get(base+'/statistics?band=0', headers=HEADERS).status_code == 422
    assert client.get(base+'/tiles/0/0/0.png?high=0', headers=HEADERS).status_code == 422
    assert client.get(base+'/tiles/0/0/0.png?mode=rgb', headers=HEADERS).status_code == 422
    assert client.get(base+'/statistics?v=old', headers=HEADERS).status_code == 409
    assert client.get('/api/v1/results/bad', headers=HEADERS).status_code == 404
    _, path = RasterResults().get(item['id'])
    path.unlink()
    assert client.get(base, headers=HEADERS).status_code == 404


def test_optional_raster_missing_catalog_stays_available(client, monkeypatch):
    def missing():
        raise RasterUnavailable('Rasterpaket fehlt')
    monkeypatch.setattr(APP, '_libraries', missing)
    assert client.get('/api/v1/results', headers=HEADERS).json()['raster_available'] is False


def test_page_security_and_navigation(client):
    page = client.get('/results')
    assert page.status_code == 200
    assert page.headers['x-frame-options'] == 'DENY'
    assert "connect-src 'self'" in page.headers['content-security-policy']
    assert 'Ordner einlesen' in page.text and 'integrity="sha256-' in page.text
    assert 'AERONEXUS_STATUS_TOKEN' not in page.text


def test_backend_failure_does_not_expose_filesystem(client, monkeypatch):
    def failure(self, **kw):
        raise OSError('/private/internal/path')
    monkeypatch.setattr(RasterResults, 'list', failure)
    response = client.get('/api/v1/results', headers=HEADERS)
    assert response.status_code == 503 and '/private/' not in response.text


def test_lan_same_origin_scan_allowed_cross_origin_denied(client, monkeypatch):
    monkeypatch.setenv('AERONEXUS_LAN_NO_TOKEN', '1')
    monkeypatch.setenv('AERONEXUS_LAN_HOST', '192.168.178.63')
    base = 'https://192.168.178.63:8000'
    lan = TestClient(APP.app, base_url=base, client=('192.168.178.50', 12345))
    assert lan.get('/api/v1/results').status_code == 200
    assert lan.post('/api/v1/results/scan', headers={'Origin': base, 'Sec-Fetch-Site':'same-origin'}).status_code == 200
    assert lan.post('/api/v1/results/scan', headers={'Origin':'https://evil.example','Sec-Fetch-Site':'cross-site'}).status_code == 403
    assert lan.post('/api/v1/results/scan').status_code == 403
    assert lan.get('/results', headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
