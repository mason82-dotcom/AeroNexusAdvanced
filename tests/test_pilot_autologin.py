"""Pilot 2 one-time pairing: authenticated restore, safe repeat and rollback."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/enable_pilot_autologin.py"
spec = importlib.util.spec_from_file_location("pilot_autologin", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


INDEX = """<template>
    <a-form
      layout="inline"
      :model="formState"
    >
      <a-button
        html-type="submit"
        :disabled="formState.user === '' || formState.password === ''"
        @click="onSubmit"
      >{{ $t('Login') }}</a-button>
    </a-form>
</template>
<script lang="ts" setup>
const formState: UnwrapRef<LoginBody> = reactive({
  username: 'pilot',
  password: 'pilot123',
  flag: EUserType.Pilot,
})
const isVerified = ref<boolean>(false)
onMounted(async () => {
  verifyLicense()
  if (!isVerified.value) {
    return
  }
  apiPilot.setPlatformMessage('Cloud Api Platform', '', '')
  const token = localStorage.getItem(ELocalStorageKey.Token)
  if (token) {
    await refreshToken({})
      .then(res => {
        const jsres = apiPilot.loadComponent(EComponentName.Api, {})
      })
  }
})
const onSubmit = async (e: any) => {
  await login(formState)
  .then(res => {
    localStorage.setItem(ELocalStorageKey.Flag, EUserType.Pilot.toString())
  })
}

function verifyLicense () {
  isVerified.value = apiPilot.platformVerifyLicense(CURRENT_CONFIG.appId, CURRENT_CONFIG.appKey, CURRENT_CONFIG.appLicense) &&
    apiPilot.isPlatformVerifySuccess()
}
</script>"""

HOME = """import { BindBody, bindDevice, getDeviceBySn, getPlatformInfo, getUserInfo } from '/@/api/manage'
import { EBizCode, EComponentName, EDownloadOwner, ELocalStorageKey, ERouterName, EStatusValue } from '/@/types'
import { onMounted, onUnmounted, reactive, ref } from 'vue'
let bindNum: any
onMounted(() => {
  apiPilot.onBackClickReg()
})
const confirmAgain = () => {
  exitVisible.value = true
}
"""


def test_index_auto_restore_is_protected_by_signed_pilot_jwt_and_license():
    transformed, changed = mod.render_index(INDEX)
    assert changed
    assert 'v-if="pairingRequired && !restoringSession && isVerified"' in transformed
    assert "password: 'pilot123'" not in transformed
    assert "password: ''," in transformed
    assert "html-type=\"button\"" in transformed
    assert ":disabled=\"busy || !formState.username || !formState.password\"" in transformed
    assert "apiPilot.platformVerifyLicense" in transformed
    assert "await refreshToken({})" in transformed
    assert "Number(data.user_type) === EUserType.Pilot" in transformed
    assert "res.data.username" not in transformed.split("const resumeSession = async () =>")[1].split("const forgetPilotSession")[0]
    assert "data.username === localStorage.getItem(ELocalStorageKey.Username)" in transformed
    assert "data.workspace_id === localStorage.getItem(ELocalStorageKey.WorkspaceId)" in transformed
    assert "apiPilot.loadComponent(EComponentName.Api" in transformed
    assert "await login(formState)" in transformed
    assert "Erneut verbinden" in transformed
    assert "Neu koppeln" in transformed
    assert "localStorage.removeItem(key)" in transformed
    assert "message.error('Pilot-Anmeldung fehlgeschlagen.')" in transformed
    assert "Einmalig koppeln" in transformed
    assert "AeroNexusAdvanced" in transformed
    assert "const onSubmit = async (e: any)" not in transformed


def test_home_renews_only_existing_pilot_session_without_password():
    transformed, changed = mod.render_home(HOME)
    assert changed
    assert "getUserInfo, refreshToken" in transformed
    assert "EStatusValue, EUserType" in transformed
    assert "pilotSessionTimer = setInterval(renewPilotSession" in transformed
    assert "Number(res.data.user_type) !== EUserType.Pilot" in transformed
    assert "await refreshToken({})" in transformed
    assert "apiPilot.setToken(res.data.access_token)" in transformed
    assert "clearInterval(pilotSessionTimer)" in transformed
    assert "login(" not in transformed
    assert "password" not in transformed


def test_both_transforms_idempotent():
    for renderer, original in ((mod.render_index, INDEX), (mod.render_home, HOME)):
        patched, changed = renderer(original)
        assert changed is True
        again, changed = renderer(patched)
        assert not changed
        assert patched == again


def test_refuse_unknown_pilot_ui_before_mutating():
    with pytest.raises(ValueError, match="upstream anchor"):
        mod.render_index(INDEX.replace("pilot123", "another password"))
    with pytest.raises(ValueError, match="upstream anchor"):
        mod.render_index(INDEX.replace("{{ $t('Login') }}", "Login"))
    with pytest.raises(ValueError, match="upstream anchor"):
        mod.render_home(HOME.replace("onMounted(() => {", "onMounted(async () => {"))


def test_stage_copies_origins_and_does_not_start_containers(tmp_path, capsys):
    web = tmp_path / "cloud-server/edge/runtime/upstream/web"
    (web / "src/pages/page-pilot").mkdir(parents=True)
    (web / "index.html").write_text("<title>AeroNexusAdvanced</title>")
    pilot = web / mod.INDEX
    home = web / mod.HOME
    pilot.write_text(INDEX)
    home.write_text(HOME)
    backup = tmp_path / "cloud-server/edge/pilot-session-backup"

    assert mod.run(False, web, backup) == 0
    assert pilot.read_text() == INDEX
    assert not backup.exists()

    assert mod.run(True, web, backup) == 0
    assert (backup / mod.INDEX).read_text() == INDEX
    assert (backup / mod.HOME).read_text() == HOME
    assert (backup.stat().st_mode & 0o077) == 0
    assert "const resumeSession" in pilot.read_text()
    assert "renewPilotSession" in home.read_text()
    assert mod.run(True, web, backup) == 0
    assert (backup / mod.INDEX).read_text() == INDEX
    assert "Keine Docker-Container" in capsys.readouterr().out


def test_fail_closed_when_web_source_missing(tmp_path):
    with pytest.raises(RuntimeError, match="missing"):
        mod.run(True, tmp_path / "missing", tmp_path / "backup")


def test_no_credentials_leaked_into_git_or_frontend():
    source = FILE.read_text()
    assert "PILOT_LOGIN_PASSWORD" not in source
    assert "PILOT2_LOGIN_PASSWORD" not in source
    assert "WEB_ADMIN_PASSWORD" not in source
    assert "JWT_SECRET" not in source
    assert "docker compose up" not in source
    assert "docker compose build" not in source
    assert "docker restart" not in source
    assert "localStorage.setItem(ELocalStorageKey.Password" not in source
    assert "/cloud-server/" in (ROOT / ".gitignore").read_text()
