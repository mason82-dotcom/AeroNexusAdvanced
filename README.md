# AeroNexusAdvanced

DJI enterprise integration gateway, initial development baseline.

## Providers
- FlightHub 2 Public Cloud OpenAPI V2.0 (planned)
- FlightHub 2 On-Premises OpenAPI V2.0 (planned)
- DJI Cloud API MQTT integration (planned)

**Current implementation:** read-only FastAPI provider registry, HTTPS transport foundation, health checks and tests. **No live DJI integration or flight control is implemented.** The three provider status records are placeholders and intentionally report `configured: false`.

## Development

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
uvicorn aeronexus.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs and http://127.0.0.1:8000/health.

## Docker

```bash
docker build -t aeronexusadvanced:dev .
docker run --rm -p 127.0.0.1:8000:8000 aeronexusadvanced:dev
```

## Safety
- Flight commands disabled; POST /api/v1/flight/command returns 403.
- No credentials in repository.
- API transport requires HTTPS.
- Actual DJI endpoint paths must be checked against the official provider/version specification before enabling them.
- The gateway is not yet hardened for public internet exposure.

## References
- https://fh.dji.com/user-manual/en/custom-development/open-api/public-cloud-v2.html
- https://fh.dji.com/user-manual/en/custom-development/open-api/private-cloud-v2.html
- https://github.com/alecad/dji-flighthub2-cli (unofficial; review before integration)
