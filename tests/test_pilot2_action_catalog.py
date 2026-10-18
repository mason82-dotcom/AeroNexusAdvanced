"""A fixed DJI taxonomy must never become an execution allowlist."""
from aeronexus.pilot2_action_catalog import (
    DOCUMENTED_ACTION_LABELS, PILOT2_OBSERVED_ACTIONS,
    PILOT2_OBSERVED_FIELDS, public_documented_catalog, public_pilot2_catalog,
)

def test_all_21_dji_names_have_bounded_labels_and_capabilities():
    docs = public_documented_catalog()
    observed = public_pilot2_catalog()
    assert len(docs) == 14
    assert len(observed) == 7
    assert len(set(DOCUMENTED_ACTION_LABELS) | set(PILOT2_OBSERVED_ACTIONS)) == 21
    assert all(x["status"] == "pilot2_observed_unverified"
               and x["export_supported"] is False for x in observed)
    assert {x["name"] for x in docs if x["export_supported"]} == {"takePhoto"}
    assert PILOT2_OBSERVED_FIELDS == {
        "cameraFocusType", "smartObliqueCycleMode",
        "smartObliquePoint", "minShootInterval",
    }
