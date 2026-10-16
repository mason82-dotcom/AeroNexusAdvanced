#!/usr/bin/env python3
"""Stage one-time pairing/automatic DJI Pilot 2 session restoration.

The first login still authenticates via DJI Cloud API. Later page openings
refresh the stored signed JWT; no password, license, MQTT key, or API
authentication is bypassed. Source changes only; never builds or starts Docker.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import os
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "cloud-server/edge/runtime/upstream/web"
INDEX = "src/pages/page-pilot/pilot-index.vue"
HOME = "src/pages/page-pilot/pilot-home.vue"
BACKUPS = ROOT / "cloud-server/edge/pilot-session-backup"

PILOT_TEMPLATE = """<p v-if="restoringSession" class="fz16 pb20">AeroNexusAdvanced verbindet automatisch…</p>
    <p v-if="retryNeeded && !restoringSession" class="fz16 pb20">Verbindung fehlgeschlagen. Gespeicherte Kopplung bleibt erhalten.</p>
    <a-button v-if="retryNeeded && !restoringSession" type="primary" @click="resumeSession">Erneut verbinden</a-button>
    <a-button v-if="retryNeeded && !restoringSession" @click="forgetPilotSession">Neu koppeln</a-button>
    <p v-if="pairingRequired && !restoringSession && isVerified" class="fz16 pb20">RC Plus 2 einmalig mit dem Pilot-Konto koppeln.</p>
    <p v-if="!isVerified && !restoringSession" class="fz16 pb20">DJI-Lizenz konnte nicht bestätigt werden.</p>
    <a-form
      v-if="pairingRequired && !restoringSession && isVerified"
      layout="inline" """

NEW_PILOT_LOGIC = r"""const pairingRequired = ref<boolean>(false)
const restoringSession = ref<boolean>(true)
const retryNeeded = ref<boolean>(false)
const busy = ref<boolean>(false)

// A Pilot 2 login must be independently authenticated by the cloud backend.
// No credentials are embedded in JavaScript, even on the trusted LAN.
function activatePilotApi (token: string): boolean {
  apiPilot.setComponentParam(EComponentName.Api, {
    host: CURRENT_CONFIG.baseURL,
    token
  })
  const loaded = apiPilot.loadComponent(EComponentName.Api, apiPilot.getComponentParam(EComponentName.Api))
  if (!loaded) {
    message.error(t('Failed to load api module.'))
    return false
  }
  apiPilot.setToken(token)
  return true
}

function isPilotIdentity (data: any): boolean {
  return !!data?.access_token &&
    Number(data.user_type) === EUserType.Pilot &&
    typeof data.username === 'string' &&
    typeof data.workspace_id === 'string' &&
    data.username !== '' && data.workspace_id !== ''
}

// Restored identity must match the device's original pairing. An admin JWT
// or a switched workspace is never silently accepted as a Pilot session.
function isRestoredIdentity (data: any): boolean {
  return isPilotIdentity(data) &&
    data.username === localStorage.getItem(ELocalStorageKey.Username) &&
    data.workspace_id === localStorage.getItem(ELocalStorageKey.WorkspaceId)
}

const resumeSession = async () => {
  restoringSession.value = true
  retryNeeded.value = false
  try {
    if (!isVerified.value) {
      return
    }
    const token = localStorage.getItem(ELocalStorageKey.Token)
    if (!token || localStorage.getItem(ELocalStorageKey.Flag) !== EUserType.Pilot.toString()) {
      pairingRequired.value = true
      return
    }
    const res = await refreshToken({})
    if (res.code !== 0 || !isRestoredIdentity(res.data)) {
      throw new Error('Invalid or unpaired Pilot session')
    }
    if (!activatePilotApi(res.data.access_token)) {
      throw new Error('DJI Pilot 2 API bridge unavailable')
    }
    localStorage.setItem(ELocalStorageKey.Token, res.data.access_token)
    await root.$router.push(ERouterName.PILOT_HOME)
  } catch (_) {
    // Never auto-submit any stored password. Offline or stale sessions
    // retain the signed token; the operator can retry or explicitly re-pair.
    retryNeeded.value = true
  } finally {
    restoringSession.value = false
  }
}

const forgetPilotSession = () => {
  // Explicit operator action only; keep non-auth preferences intact.
  for (const key of [
    ELocalStorageKey.Token, ELocalStorageKey.Username, ELocalStorageKey.UserId,
    ELocalStorageKey.WorkspaceId, ELocalStorageKey.Flag,
    ELocalStorageKey.PlatformName, ELocalStorageKey.WorkspaceName,
    ELocalStorageKey.WorkspaceDesc
  ]) {
    localStorage.removeItem(key)
  }
  retryNeeded.value = false
  pairingRequired.value = true
  formState.password = ''
}

onMounted(async () => {
  try {
    verifyLicense()
  } catch (_) {
    message.error('DJI Pilot 2 Bridge nicht verfügbar.')
  }
  if (!isVerified.value) {
    restoringSession.value = false
    return
  }
  apiPilot.setPlatformMessage('AeroNexusAdvanced', '', '')
  await resumeSession()
})

// First pairing only: the normal authenticated Pilot 2 login remains.
const onSubmit = async (e?: Event) => {
  e?.preventDefault()
  if (busy.value || !isVerified.value ||
      !formState.username || !formState.password) {
    return
  }
  busy.value = true
  try {
    const res = await login(formState)
    if (res.code !== 0 || !isPilotIdentity(res.data)) {
      message.error('Pilot-Anmeldung fehlgeschlagen.')
      return
    }
    if (!activatePilotApi(res.data.access_token)) {
      return
    }
    localStorage.setItem(ELocalStorageKey.Token, res.data.access_token)
    localStorage.setItem(ELocalStorageKey.WorkspaceId, res.data.workspace_id)
    localStorage.setItem(ELocalStorageKey.UserId, res.data.user_id)
    localStorage.setItem(ELocalStorageKey.Username, res.data.username)
    localStorage.setItem(ELocalStorageKey.Flag, EUserType.Pilot.toString())
    message.success('RC Plus 2 mit AeroNexusAdvanced gekoppelt.')
    await root.$router.push(ERouterName.PILOT_HOME)
  } catch (_) {
    message.error('Pilot-Anmeldung nicht verfügbar.')
  } finally {
    // Plaintext credentials never persist on the controller or in logs.
    formState.password = ''
    busy.value = false
  }
}

"""

HOME_REFRESher = r"""
// Keep the signed Pilot session current while Pilot 2 stays open overnight.
// Refresh only with an existing server-issued JWT, never with credentials.
// If offline, keep the last token for retry on the next WebView opening.
const PILOT_SESSION_REFRESH_MS = 2 * 60 * 60 * 1000
let pilotSessionTimer: ReturnType<typeof setInterval> | undefined

async function renewPilotSession () {
  if (localStorage.getItem(ELocalStorageKey.Flag) !== EUserType.Pilot.toString() ||
      !localStorage.getItem(ELocalStorageKey.Token)) {
    return
  }
  try {
    const res = await refreshToken({})
    if (res.code !== 0 || !res.data?.access_token ||
        Number(res.data.user_type) !== EUserType.Pilot ||
        res.data.username !== localStorage.getItem(ELocalStorageKey.Username) ||
        res.data.workspace_id !== localStorage.getItem(ELocalStorageKey.WorkspaceId)) {
      return
    }
    apiPilot.setToken(res.data.access_token)
    localStorage.setItem(ELocalStorageKey.Token, res.data.access_token)
  } catch (_) {
    // A brief WLAN outage must not clear the paired controller's session.
  }
}
"""

def once(text: str, original: str, replacement: str, label: str) -> str:
    if text.count(original) != 1:
        raise ValueError(f"{label}: expected unique upstream anchor, found {text.count(original)}")
    return text.replace(original, replacement, 1)


def render_index(content: str) -> tuple[str, bool]:
    if "const pairingRequired = ref<boolean>(false)" in content:
        if ("const resumeSession = async () =>" in content and
                "v-if=\"pairingRequired" in content and
                "username: 'pilot'," in content and
                "password: ''," in content):
            return content, False
        raise ValueError("Pilot login has incomplete or conflicting auto-pairing changes")
    updated = once(
        content,
        '    <a-form\n      layout="inline"',
        '    ' + PILOT_TEMPLATE.replace("    <a-form", "<a-form").rstrip(),
        "pilot login form",
    )
    updated = once(
        updated,
        ':disabled="formState.user === \'\' || formState.password === \'\'"',
        ':disabled="busy || !formState.username || !formState.password"',
        "pilot form disabled state",
    )
    updated = once(updated, 'html-type="submit"', 'html-type="button"',
                   "pilot button prevents implicit form submit")
    updated = once(updated, "{{ $t('Login') }}", "Einmalig koppeln",
                   "German pilot login button")
    updated = once(updated, "password: 'pilot123',", "password: '',",
                   "insecure default pilot password")
    updated = once(
        updated, "const isVerified = ref<boolean>(false)\n",
        "const isVerified = ref<boolean>(false)\n" + NEW_PILOT_LOGIC,
        "license ref + Pilot pairing flow",
    )
    start = updated.find("onMounted(async () => {\n  verifyLicense()\n")
    if start == -1:
        raise ValueError("Legacy Pilot mounted block missing")
    finish = updated.find("\nfunction verifyLicense () {", start)
    if finish == -1:
        raise ValueError("Legacy Pilot verifyLicense block missing")
    # The original auto-refresh/login block must still exist and be unique.
    removed = updated[start:finish]
    if ("const onSubmit = async (e: any) => {" not in removed or
            "await refreshToken({})" not in removed or
            "localStorage.setItem(ELocalStorageKey.Flag" not in removed):
        raise ValueError("Legacy Pilot login behavior unexpectedly changed")
    updated = updated[:start] + updated[finish + 1:]
    # NEW_PILOT_LOGIC includes onMounted and onSubmit; remove old equivalents.
    if updated.count("onMounted(async () => {") != 1:
        raise ValueError("Pilot mount handler is not unique")
    if updated.count("function verifyLicense () {") != 1:
        raise ValueError("DJI license validation must remain intact")
    if "apiPilot.platformVerifyLicense" not in updated:
        raise ValueError("DJI license validation removed")
    if "const onSubmit = async (e: any)" in updated:
        raise ValueError("Legacy Pilot login handler still present")
    if "password: 'pilot123'" in updated:
        raise ValueError("Default Pilot credential still present")
    return updated, True


def render_home(content: str) -> tuple[str, bool]:
    if "const PILOT_SESSION_REFRESH_MS" in content:
        if ("pilotSessionTimer = setInterval" in content and
                "clearInterval(pilotSessionTimer)" in content):
            return content, False
        raise ValueError("Incomplete Pilot home session refresh")
    result = once(
        content,
        "bindDevice, getDeviceBySn, getPlatformInfo, getUserInfo } from '/@/api/manage'",
        "bindDevice, getDeviceBySn, getPlatformInfo, getUserInfo, refreshToken } from '/@/api/manage'",
        "Pilot home refresh endpoint import",
    )
    result = once(
        result,
        "EDownloadOwner, ELocalStorageKey, ERouterName, EStatusValue } from '/@/types'",
        "EDownloadOwner, ELocalStorageKey, ERouterName, EStatusValue, EUserType } from '/@/types'",
        "Pilot home user type guard",
    )
    result = once(result, "let bindNum: any\n", "let bindNum: any\n" + HOME_REFRESher,
                  "Pilot home session maintenance")
    result = once(
        result,
        "onMounted(() => {\n  apiPilot.onBackClickReg()",
        "onMounted(() => {\n  pilotSessionTimer = setInterval(renewPilotSession, PILOT_SESSION_REFRESH_MS)\n  apiPilot.onBackClickReg()",
        "Pilot home timer start",
    )
    result = once(
        result,
        "const confirmAgain = () => {",
        "onUnmounted(() => {\n  if (pilotSessionTimer) clearInterval(pilotSessionTimer)\n})\n\nconst confirmAgain = () => {",
        "Pilot home timer cleanup",
    )
    return result, True


def atomic_write(path: Path, contents: str) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".pilot-autologin-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(contents)
        os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(apply: bool, web: Path = WEB, backups: Path = BACKUPS) -> int:
    if not web.is_dir() or not (web / "index.html").exists():
        raise RuntimeError("Migrated Pilot 2 web sources are missing")
    paths = (web / INDEX, web / HOME)
    originals = {p: p.read_text(encoding="utf-8") for p in paths}
    planned = {}
    for path, transform in ((paths[0], render_index), (paths[1], render_home)):
        patched, changed = transform(originals[path])
        if changed:
            planned[path] = patched
    print("Pilot-2-Autologin:", "bereits aktiviert" if not planned else
          f"{len(planned)} Dateien zur Änderung erkannt")
    if not apply:
        print("NUR PRÜFUNG: keine Dateien oder Container verändert")
        print("Zum Vorbereiten: python3 scripts/enable_pilot_autologin.py --apply")
        return 0
    backups.mkdir(parents=True, exist_ok=True, mode=0o700)
    backups.chmod(0o700)
    # Validate that original backups won't be overwritten after a partial run.
    for path in planned:
        original_backup = backups / path.relative_to(web)
        if original_backup.exists() and original_backup.read_text(encoding="utf-8") != originals[path]:
            # For a repeated partially-applied run the source may have
            # diverged from backup, but render_* refuses unknown modifications.
            if "const pairingRequired" not in originals[path] and "PILOT_SESSION_REFRESH_MS" not in originals[path]:
                raise RuntimeError("Conflicting old Pilot pairing backup: " +
                                   str(path.relative_to(web)))
    for path, replacement in planned.items():
        target_backup = backups / path.relative_to(web)
        target_backup.parent.mkdir(parents=True, exist_ok=True)
        if not target_backup.exists():
            shutil.copy2(path, target_backup)
        atomic_write(path, replacement)
        print("Vorbereitet:", str(path.relative_to(web)))
    print("Keine Docker-Container gestartet oder verändert.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write local files")
    args = parser.parse_args(argv)
    try:
        return run(args.apply)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"PILOT-AUTOLOGIN: ABGEBROCHEN ({type(exc).__name__}): {exc}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
