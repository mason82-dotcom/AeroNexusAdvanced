#!/usr/bin/env bash
# Install the DJI Thermal SDK (TSDK, tested v1.8 20250829) for the AeroNexusAdvanced
# thermal module (/thermal), without root and outside the repository.
#
#   deploy/pi/install-thermal-sdk.sh ~/Downloads/dji_thermal_sdk_v1.8_<date>.zip
#
# The SDK is proprietary (DJI license, https://www.dji.com/downloads/softwares/dji-thermal-sdk)
# and is NEVER committed. DJI ships Linux x86/x64 builds only. On ARM64 (Raspberry Pi 5,
# 16 KiB pages; qemu-user cannot map the SDK libraries) the x64 tool runs under Box64:
#   * box64 (arm64) via `apt-get download` from the configured, signed APT sources,
#   * x86_64 libstdc++6 / libgcc-s1 / libgomp1 from deb.debian.org, verified against the
#     Debian InRelease signature (gpgv + debian-archive-keyring) and SHA256.
# Nothing is installed system-wide; existing installs are replaced atomically.
set -euo pipefail
umask 022

ZIP="${1:?usage: $0 <dji_thermal_sdk_*.zip>}"
TSDK_DEST="${AERONEXUS_DJI_TSDK_DIR:-$HOME/.local/opt/dji-tsdk}"
BOX_DEST="${AERONEXUS_BOX64_HOME:-$HOME/.local/opt/aeronexus-box64}"
SUITE="${AERONEXUS_DEBIAN_SUITE:-trixie}"
MIRROR="https://deb.debian.org/debian"
KEYRING=/usr/share/keyrings/debian-archive-keyring.gpg

for tool in unzip curl gpgv xz sha256sum dpkg-deb; do
  command -v "$tool" >/dev/null || { echo "ERROR: $tool is required" >&2; exit 2; }
done
[ -f "$ZIP" ] || { echo "ERROR: $ZIP not found" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---- DJI Thermal SDK ---------------------------------------------------------------
unzip -q "$ZIP" -d "$TMP/sdk"
TOOL="$(find "$TMP/sdk" -type f -path '*utility/bin/linux/release_x64/dji_irp' | head -1)"
LIBS="$(find "$TMP/sdk" -type d -path '*tsdk-core/lib/linux/release_x64' | head -1)"
if [ -z "$TOOL" ] || [ -z "$LIBS" ] || [ ! -f "$LIBS/libdirp.so" ]; then
  echo "ERROR: $ZIP has no Linux x64 dji_irp/libdirp.so (unexpected SDK layout)" >&2
  exit 1
fi
mkdir -p "$TMP/tsdk/bin"
cp -a "$LIBS"/. "$TMP/tsdk/bin/"
cp -a "$TOOL" "$TMP/tsdk/bin/dji_irp"
chmod 0755 "$TMP/tsdk/bin/dji_irp"
find "$TMP/sdk" -maxdepth 2 -iname 'license*' -exec cp {} "$TMP/tsdk/" \;
sha256sum "$ZIP" | awk '{print $1}' > "$TMP/tsdk/SOURCE_SHA256"
mkdir -p "$(dirname "$TSDK_DEST")"
rm -rf "$TSDK_DEST.new" && mv "$TMP/tsdk" "$TSDK_DEST.new"
rm -rf "$TSDK_DEST.old"; [ -e "$TSDK_DEST" ] && mv "$TSDK_DEST" "$TSDK_DEST.old"
mv "$TSDK_DEST.new" "$TSDK_DEST" && rm -rf "$TSDK_DEST.old"
echo "DJI Thermal SDK (linux x64) -> $TSDK_DEST/bin"

ARCH="$(uname -m)"
if [ "$ARCH" != "x86_64" ]; then
  # ---- Box64 (signed APT source) ----------------------------------------------------
  mkdir -p "$TMP/box" && (cd "$TMP/box" && apt-get download -q box64 >/dev/null)
  dpkg-deb -x "$TMP"/box/box64_*.deb "$TMP/box64"

  # ---- x86_64 runtime libraries, verified against the signed Debian index ----------
  curl -fsSL --proto '=https' "$MIRROR/dists/$SUITE/InRelease" -o "$TMP/InRelease"
  gpgv --keyring "$KEYRING" --output "$TMP/Release" "$TMP/InRelease" 2>/dev/null \
    || { echo "ERROR: Debian InRelease signature invalid" >&2; exit 1; }
  want="$(awk '/^SHA256:/{f=1;next} /^[^ ]/{f=0} f && $3=="main/binary-amd64/Packages.xz"{print $1}' "$TMP/Release")"
  [ -n "$want" ] || { echo "ERROR: Packages.xz hash missing in Release" >&2; exit 1; }
  curl -fsSL --proto '=https' "$MIRROR/dists/$SUITE/main/binary-amd64/Packages.xz" -o "$TMP/Packages.xz"
  echo "$want  $TMP/Packages.xz" | sha256sum -c --quiet -
  xz -dc "$TMP/Packages.xz" > "$TMP/Packages"
  mkdir -p "$TMP/x86libs"
  for pkg in libstdc++6 libgcc-s1 libgomp1; do
    read -r file sum < <(awk -v p="$pkg" '
      /^Package: /{cur=$2} /^Filename: /{fn=$2} /^SHA256: /{sh=$2}
      /^$/{ if (cur==p && fn!="") {print fn, sh; exit} cur=""; fn=""; sh="" }' "$TMP/Packages")
    [ -n "${file:-}" ] || { echo "ERROR: $pkg not in Debian $SUITE amd64 index" >&2; exit 1; }
    curl -fsSL --proto '=https' "$MIRROR/$file" -o "$TMP/$pkg.deb"
    echo "$sum  $TMP/$pkg.deb" | sha256sum -c --quiet -
    dpkg-deb -x "$TMP/$pkg.deb" "$TMP/x86root"
    echo "verified $pkg ($(basename "$file"))"
  done
  cp -L "$TMP"/x86root/usr/lib/x86_64-linux-gnu/{libstdc++.so.6,libgcc_s.so.1,libgomp.so.1} "$TMP/x86libs/"
  mkdir -p "$TMP/boxhome" && mv "$TMP/box64/usr" "$TMP/boxhome/usr" && mv "$TMP/x86libs" "$TMP/boxhome/x86libs"
  mkdir -p "$(dirname "$BOX_DEST")"
  rm -rf "$BOX_DEST.old"; [ -e "$BOX_DEST" ] && mv "$BOX_DEST" "$BOX_DEST.old"
  mv "$TMP/boxhome" "$BOX_DEST" && rm -rf "$BOX_DEST.old"
  echo "Box64 + x86_64 runtime -> $BOX_DEST"
fi

# ---- smoke test -------------------------------------------------------------------------
cd "$TMP"
if [ "$ARCH" = "x86_64" ]; then
  out="$(LD_LIBRARY_PATH="$TSDK_DEST/bin" "$TSDK_DEST/bin/dji_irp" -V 2>&1 || true)"
else
  out="$(BOX64_LOG=0 BOX64_NOBANNER=1 BOX64_LD_LIBRARY_PATH="$TSDK_DEST/bin:$BOX_DEST/x86libs" \
    "$BOX_DEST/usr/bin/box64" "$TSDK_DEST/bin/dji_irp" -V 2>&1 || true)"
fi
grep -qi "APP version" <<<"$out" || { echo "ERROR: dji_irp smoke test failed" >&2; exit 1; }
grep -i "APP version" <<<"$out"
cat <<EOF

Done. Add to the private .env (chmod 600) and restart the service:
  AERONEXUS_DJI_TSDK_DIR=$TSDK_DEST
  AERONEXUS_DJI_TSDK_RUNNER=auto   # native on x86_64, Box64 elsewhere
  AERONEXUS_BOX64=$BOX_DEST/usr/bin/box64
  AERONEXUS_BOX64_X86_LIBS=$BOX_DEST/x86libs
  systemctl --user restart aeronexusadvanced
EOF
