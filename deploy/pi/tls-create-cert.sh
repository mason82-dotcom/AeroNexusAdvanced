#!/usr/bin/env bash
# Provision an isolated AeroNexusAdvanced CA and an IP-SAN server certificate.
# Never overwrites existing PKI files; does not touch system trust stores.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PKI="$ROOT/config/pki"

if [[ $# -ne 1 ]]; then
  printf 'Usage: bash deploy/pi/tls-create-cert.sh <PI_PRIVATE_IPV4>\n' >&2
  exit 2
fi
IP="$1"
python3 - "$IP" <<'PY'
import ipaddress, sys
try:
    ip = ipaddress.ip_address(sys.argv[1])
except ValueError:
    raise SystemExit("ERROR: invalid IPv4 address")
private = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
if ip.version != 4 or not any(ip in n for n in private):
    raise SystemExit("ERROR: supply the Raspberry Pi's private (RFC 1918) IPv4 LAN address")
PY
command -v openssl >/dev/null || { printf 'openssl not installed\n' >&2; exit 2; }
for file in ca.key ca.crt server.key server.crt; do
  if [[ -e "$PKI/$file" ]]; then
    printf 'REFUSED: %s exists. No files overwritten.\n' "$PKI/$file" >&2
    exit 3
  fi
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
printf 'Creating AeroNexusAdvanced local CA and server certificate for %s ...\n' "$IP"
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -sha256 \
  -days 1095 -keyout "$TMP/ca.key" -out "$TMP/ca.crt" \
  -subj "/CN=AeroNexusAdvanced Local CA" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" >/dev/null 2>&1
openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -sha256 \
  -keyout "$TMP/server.key" -out "$TMP/server.csr" \
  -subj "/CN=AeroNexusAdvanced-Pi" >/dev/null 2>&1
cat > "$TMP/server.ext" <<EXT
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=IP:$IP
EXT
# 365 days: below the 398-day limit browsers enforce for server certificates.
openssl x509 -req -sha256 -days 365 -in "$TMP/server.csr" \
  -CA "$TMP/ca.crt" -CAkey "$TMP/ca.key" -CAcreateserial \
  -extfile "$TMP/server.ext" -out "$TMP/server.crt" >/dev/null 2>&1
openssl verify -verify_ip "$IP" -CAfile "$TMP/ca.crt" "$TMP/server.crt" >/dev/null

mkdir -p "$PKI"
install -m 600 "$TMP/ca.key" "$PKI/ca.key"
install -m 644 "$TMP/ca.crt" "$PKI/ca.crt"
install -m 600 "$TMP/server.key" "$PKI/server.key"
install -m 644 "$TMP/server.crt" "$PKI/server.crt"
printf 'Done: %s (private keys 0600, server certificate valid 365 days).\n' "$PKI"
printf 'Install ONLY ca.crt on your viewing devices. Never publish config/pki.\n'
printf 'Add to .env:\n  AERONEXUS_BIND=%s\n  AERONEXUS_TLS_CERT=%s\n  AERONEXUS_TLS_KEY=%s\n' \
  "$IP" "$PKI/server.crt" "$PKI/server.key"
