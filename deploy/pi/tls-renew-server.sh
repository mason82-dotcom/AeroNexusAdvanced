#!/usr/bin/env bash
# Renew only the server certificate with the existing AeroNexusAdvanced CA,
# so viewing devices keep trusting ca.crt. The old pair is kept as *.old.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PKI="$ROOT/config/pki"
if [[ $# -ne 1 ]]; then
  printf 'Usage: bash deploy/pi/tls-renew-server.sh <PI_PRIVATE_IPV4>\n' >&2
  exit 2
fi
IP="$1"
for file in ca.key ca.crt; do
  [[ -r "$PKI/$file" ]] || { printf 'Missing %s; run tls-create-cert.sh first.\n' "$PKI/$file" >&2; exit 2; }
done
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -sha256 \
  -keyout "$TMP/server.key" -out "$TMP/server.csr" -subj "/CN=AeroNexusAdvanced-Pi" >/dev/null 2>&1
printf 'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:%s\n' \
  "$IP" > "$TMP/server.ext"
openssl x509 -req -sha256 -days 365 -in "$TMP/server.csr" -CA "$PKI/ca.crt" -CAkey "$PKI/ca.key" \
  -CAcreateserial -CAserial "$TMP/ca.srl" -extfile "$TMP/server.ext" -out "$TMP/server.crt" >/dev/null 2>&1
openssl verify -verify_ip "$IP" -CAfile "$PKI/ca.crt" "$TMP/server.crt" >/dev/null
for file in server.key server.crt; do
  [[ -e "$PKI/$file" ]] && mv "$PKI/$file" "$PKI/$file.old"
done
install -m 600 "$TMP/server.key" "$PKI/server.key"
install -m 644 "$TMP/server.crt" "$PKI/server.crt"
printf 'Renewed %s/server.crt for %s (365 days). Restart: systemctl --user restart aeronexusadvanced\n' "$PKI" "$IP"
printf 'Expires: %s\n' "$(openssl x509 -enddate -noout -in "$PKI/server.crt" | cut -d= -f2)"
