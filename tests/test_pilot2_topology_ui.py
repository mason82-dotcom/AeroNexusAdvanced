"""Direct Pilot 2 topology viewer is read-only and request driven."""
from aeronexus.studio_page import render_studio


def test_topology_readonly_view_is_user_initiated():
    page = render_studio()
    assert 'id="pilot2-topology-refresh"' in page
    assert 'id="pilot2-topology-state"' in page
    assert 'id="pilot2-topology-grid"' in page
    block = page[page.index("async function loadPilot2Topology()"):page.index("async function showFleetOnMap()")]
    assert 'api("/api/v1/local-cloud/topology")' in block
    assert "cardText(" in block
    assert "innerHTML" not in block
    assert "saveMission" not in block
    assert "publish(" not in block
    assert 'button.disabled=true' in block and 'button.disabled=false' in block
    assert '$("pilot2-topology-refresh").addEventListener("click",loadPilot2Topology)' in page


def test_topology_status_distinguishes_online_offline_unknown_and_links():
    page = render_studio()
    block = page[page.index("async function loadPilot2Topology()"):page.index("async function showFleetOnMap()")]
    assert 'device.online===true' in block
    assert 'device.online===false' in block
    assert 'unknown=data.devices.length-online-offline' in block
    assert 'Cloud-Momentaufnahme' in block
    assert 'data.links.filter(' in block
    assert 'counterpartRole' in block
    assert 'Zugeordnet: ' in block
    assert 'Keine Zuordnung gemeldet' in block
    assert 'cardText(card,"p","note"' in block
    assert 'innerHTML' not in block
