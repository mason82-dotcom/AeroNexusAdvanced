import pytest
from aeronexus.adapters import DJIAdapter

@pytest.mark.parametrize("url", ["http://example.com", "https://user:pass@example.com", "file:///etc/passwd"])
def test_reject_unsafe_base_url(url):
    with pytest.raises(ValueError):
        DJIAdapter(url, "token")

def test_reject_invalid_path():
    import asyncio
    adapter = DJIAdapter("https://example.com", "token")
    with pytest.raises(ValueError):
        asyncio.run(adapter.get("//evil.example/path"))
