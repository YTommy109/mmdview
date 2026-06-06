# tests/unit/test_update_installer.py
"""update_installer と update_mount の単体テスト。"""

from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import backend.services.update_installer as installer
import backend.services.update_mount as mount_module
import backend.services.update_service as svc


@pytest.fixture(autouse=True)
def reset_download_state():
    svc.update_service._reset_for_test()
    yield
    svc.update_service._reset_for_test()


def _make_plist_bytes(mount_point: str) -> bytes:
    data = {
        "system-entities": [
            {"dev-entry": "/dev/disk4"},
            {"dev-entry": "/dev/disk4s1", "content-hint": "Apple_partition_map"},
            {
                "dev-entry": "/dev/disk4s2",
                "content-hint": "Apple_HFS",
                "mount-point": mount_point,
            },
        ]
    }
    return plistlib.dumps(data)


def test_get_app_path_frozen環境():
    fake_exe = "/Applications/mmdview.app/Contents/MacOS/mmdview"
    with patch.object(sys, "frozen", True, create=True):
        with patch.object(sys, "executable", fake_exe):
            result = installer._get_app_path()
    assert result == Path("/Applications/mmdview.app")


def test_get_app_path_開発環境():
    with patch.object(sys, "frozen", False, create=True):
        result = installer._get_app_path()
    assert result is None


def test_write_updater_script_内容検証(tmp_path):
    app_path = Path("/Applications/mmdview.app")
    mount_point = Path("/Volumes/mmdview")
    new_app_src = Path("/Volumes/mmdview/mmdview.app")
    dmg_path = Path("/Users/user/Downloads/mmdview-update.dmg")
    script_path = tmp_path / "mmdview-updater.sh"

    with patch.object(installer, "_SCRIPT_PATH", script_path):
        result = installer._write_updater_script(app_path, mount_point, new_app_src, dmg_path)

    content = result.read_text()
    assert "hdiutil detach" in content
    assert f'open "{app_path}"' in content
    assert f'cp -R "{new_app_src}"' in content
    assert "sleep 3" in content
    assert f'rm -f "{dmg_path}"' in content


def test_mount_dmg_plist_パースで正しいマウントポイントを返す(tmp_path):
    dmg_file = tmp_path / "test.dmg"
    dmg_file.touch()
    mock_result = MagicMock()
    mock_result.stdout = _make_plist_bytes("/Volumes/mmdview")

    with patch("subprocess.run", return_value=mock_result):
        result = mount_module.mount_dmg(str(dmg_file))

    assert result == Path("/Volumes/mmdview")


def test_mount_dmg_hdiutil失敗時はNoneを返す(tmp_path):
    import subprocess

    dmg_file = tmp_path / "test.dmg"
    dmg_file.touch()
    error = subprocess.CalledProcessError(1, "hdiutil")

    with patch("subprocess.run", side_effect=[MagicMock(), error]):
        result = mount_module.mount_dmg(str(dmg_file))

    assert result is None


def test_mount_dmg_plistパース失敗時はNoneを返す(tmp_path):
    dmg_file = tmp_path / "test.dmg"
    dmg_file.touch()
    mock_result = MagicMock()
    mock_result.stdout = b"not valid plist data"

    with patch("subprocess.run", return_value=mock_result):
        result = mount_module.mount_dmg(str(dmg_file))

    assert result is None


def test_mount_dmg_mount_pointなしの場合はNoneを返す(tmp_path):
    dmg_file = tmp_path / "test.dmg"
    dmg_file.touch()
    data = {"system-entities": [{"dev-entry": "/dev/disk4"}]}
    mock_result = MagicMock()
    mock_result.stdout = plistlib.dumps(data)

    with patch("subprocess.run", return_value=mock_result):
        result = mount_module.mount_dmg(str(dmg_file))

    assert result is None


def test_mount_dmg_MMDVIEW_MOCK_DMG環境変数でモックマウントポイントを返す():
    with patch.dict(os.environ, {"MMDVIEW_MOCK_DMG": "/tmp/mmdview-test.dmg"}):
        with patch.object(Path, "mkdir"):
            with patch.object(Path, "exists", return_value=True):
                result = mount_module.mount_dmg("/tmp/mmdview-test.dmg")
    assert result == mount_module._MOCK_VOLUME


def test_install_update_dmgなしは_no_dmg_を返す():
    svc.update_service._download_state.update({"percent": 0, "status": "idle", "dmg_path": None})
    result = installer.install_update()
    assert result == "no_dmg"


def test_install_update_マウント失敗は_mount_failed_を返す(tmp_path):
    import subprocess

    dmg_file = tmp_path / "test.dmg"
    dmg_file.touch()
    svc.update_service._download_state.update(
        {"percent": 100, "status": "done", "dmg_path": str(dmg_file)}
    )
    error = subprocess.CalledProcessError(1, "hdiutil")

    with patch("subprocess.run", side_effect=[MagicMock(), error]):
        result = installer.install_update()

    assert result == "mount_failed"


def test_install_update_appなしは_no_app_を返す(tmp_path):
    dmg_file = tmp_path / "test.dmg"
    dmg_file.touch()
    svc.update_service._download_state.update(
        {"percent": 100, "status": "done", "dmg_path": str(dmg_file)}
    )
    plist_bytes = _make_plist_bytes("/Volumes/Test")
    mock_result = MagicMock()
    mock_result.stdout = plist_bytes

    with patch("subprocess.run", return_value=mock_result):
        with patch.object(Path, "glob", return_value=[]):
            result = installer.install_update()

    assert result == "no_app"


def test_install_update_開発環境では_not_frozen_を返す(tmp_path):
    dmg_file = tmp_path / "test.dmg"
    dmg_file.touch()
    svc.update_service._download_state.update(
        {"percent": 100, "status": "done", "dmg_path": str(dmg_file)}
    )
    plist_bytes = _make_plist_bytes("/Volumes/Test")
    mock_result = MagicMock()
    mock_result.stdout = plist_bytes

    with patch.object(sys, "frozen", False, create=True):
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(Path, "glob", return_value=[Path("/Volumes/Test/mmdview.app")]):
                result = installer.install_update()

    assert result == "not_frozen"


def test_get_app_path_MMDVIEW_MOCK_FROZEN環境変数が設定されている場合モックパスを返す():
    with patch.dict(os.environ, {"MMDVIEW_MOCK_FROZEN": "1"}):
        with patch.object(Path, "mkdir"):
            result = installer._get_app_path()
    assert result == Path("/tmp/mmdview-mock.app")


def test_install_update_MMDVIEW_MOCK_FROZEN環境変数でフローを実行できる(tmp_path):
    dmg_file = tmp_path / "test.dmg"
    dmg_file.touch()
    svc.update_service._download_state.update(
        {"percent": 100, "status": "done", "dmg_path": str(dmg_file)}
    )
    plist_bytes = _make_plist_bytes("/Volumes/Test")
    mock_run_result = MagicMock()
    mock_run_result.stdout = plist_bytes
    script_path = tmp_path / "mmdview-updater.sh"

    with patch.dict(os.environ, {"MMDVIEW_MOCK_FROZEN": "1"}):
        with patch("subprocess.run", return_value=mock_run_result):
            with patch.object(Path, "glob", return_value=[Path("/Volumes/Test/mmdview.app")]):
                with patch.object(installer, "_SCRIPT_PATH", script_path):
                    with patch("subprocess.Popen") as mock_popen:
                        with patch("os._exit") as mock_os_exit:
                            installer.install_update()

    mock_os_exit.assert_called_once_with(0)
    mock_popen.assert_called_once()


def test_install_update_成功時はPopenを呼びos_exitする(tmp_path):
    dmg_file = tmp_path / "test.dmg"
    dmg_file.touch()
    svc.update_service._download_state.update(
        {"percent": 100, "status": "done", "dmg_path": str(dmg_file)}
    )
    plist_bytes = _make_plist_bytes("/Volumes/Test")
    mock_run_result = MagicMock()
    mock_run_result.stdout = plist_bytes
    fake_exe = "/Applications/mmdview.app/Contents/MacOS/mmdview"
    script_path = tmp_path / "mmdview-updater.sh"

    with patch("subprocess.run", return_value=mock_run_result):
        with patch.object(Path, "glob", return_value=[Path("/Volumes/Test/mmdview.app")]):
            with patch.object(sys, "frozen", True, create=True):
                with patch.object(sys, "executable", fake_exe):
                    with patch.object(installer, "_SCRIPT_PATH", script_path):
                        with patch("subprocess.Popen") as mock_popen:
                            with patch("os._exit") as mock_os_exit:
                                installer.install_update()

    mock_os_exit.assert_called_once_with(0)
    mock_popen.assert_called_once_with(["bash", str(script_path)])
