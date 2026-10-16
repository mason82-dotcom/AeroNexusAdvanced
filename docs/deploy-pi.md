# Running AeroNexusAdvanced on the Raspberry Pi (systemd + HTTPS)

AeroNexusAdvanced runs as a systemd **user** service (no sudo) and serves the
dashboard over HTTPS on the Pi's LAN address with a project-specific local
CA. Plain HTTP on a LAN address is refused unless explicitly allowed.

## Files

| Path | Purpose |
|---|---|
| `deploy/pi/tls-create-cert.sh <IP>` | creates `config/pki/` (CA + IP-SAN server certificate), never overwrites |
| `deploy/pi/tls-renew-server.sh <IP>` | new server certificate with the existing CA (devices keep trusting it) |
| `deploy/pi/run-server.sh` | launcher: reads `.env`, refuses unsafe configs, starts uvicorn with TLS |
| `deploy/pi/aeronexusadvanced.service.in` | unit template (`Restart=always`, `NoNewPrivileges`, `UMask=0077`) |
| `deploy/pi/install-service.sh` | renders the unit into `~/.config/systemd/user/` and enables it |
| `config/pki/` | **gitignored**; `ca.key` and `server.key` are 0600 |

`run-server.sh` exit codes: `2` missing configuration (no `.env`, no
virtualenv, unreadable TLS file), `3` refused configuration (`.env` not
0600, LAN bind without TLS). systemd does not restart on 2/3
(`RestartPreventExitStatus`), so fix the configuration and restart.

## Setup

```bash
cd ~/Projekte/AeroNexusAdvanced
bash deploy/pi/tls-create-cert.sh 192.168.178.63
# add the printed AERONEXUS_BIND / AERONEXUS_TLS_CERT / AERONEXUS_TLS_KEY
# (and optionally AERONEXUS_PORT=8000) to .env, chmod 600 .env
bash deploy/pi/install-service.sh
systemctl --user restart aeronexusadvanced
curl --cacert config/pki/ca.crt https://192.168.178.63:8000/health
```

Boot start without login requires linger (`loginctl show-user $USER -p
Linger` = `yes`; enable with `loginctl enable-linger $USER`).

## Operation

```bash
systemctl --user status aeronexusadvanced
systemctl --user restart aeronexusadvanced     # after .env or code changes
journalctl --user -u aeronexusadvanced -f
```

Do not start additional uvicorn instances on the same port; the service
owns `192.168.178.63:8000`.

## Trusting the CA on viewing devices

Copy **only** `config/pki/ca.crt` (never `ca.key`) to the device and install
it as a trusted CA certificate:

- Android: Settings -> Security -> Encryption & credentials -> Install a
  certificate -> CA certificate.
- iOS/iPadOS: open the file, install the profile, then Settings -> General ->
  About -> Certificate Trust Settings -> enable full trust.
- Windows: `certmgr.msc` -> Trusted Root Certification Authorities -> Import.
- macOS: Keychain Access -> System -> import, set "Always Trust".
- Firefox uses its own store: Settings -> Privacy & Security -> Certificates
  -> View Certificates -> Authorities -> Import.

Then open `https://192.168.178.63:8000/status`. The CA is valid for 3 years
and can only sign certificates (`pathlen:0`); keep `ca.key` on the Pi.

## Renewal

The server certificate is valid for 365 days (browser limit 398 days).

```bash
openssl x509 -enddate -noout -in config/pki/server.crt
bash deploy/pi/tls-renew-server.sh 192.168.178.63
systemctl --user restart aeronexusadvanced
```

If the Pi's LAN address changes, renew with the new IP and update
`AERONEXUS_BIND` in `.env`.
