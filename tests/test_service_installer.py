from catpoop.service.installer import install, secrets_file, uninstall, unit_folder
from catpoop.service.unit_file import UNIT_NAME


class FakeServiceManager:
    def __init__(self, folder=None):
        self.calls: list[tuple[str, ...]] = []
        self.folder = folder

    def reload(self) -> None:
        self.calls.append(("reload",))

    def enable_now(self, unit: str) -> None:
        exists = self.folder is None or (self.folder / unit).is_file()
        self.calls.append(("enable_now", unit, str(exists)))

    def disable_now(self, unit: str) -> None:
        self.calls.append(("disable_now", unit))


def test_install_writes_the_unit_then_reloads_and_starts_it(tmp_path):
    folder = tmp_path / "systemd" / "user"
    manager = FakeServiceManager(folder)
    path = install("[Unit]\n", folder, manager)
    assert path == folder / UNIT_NAME
    assert path.read_text() == "[Unit]\n"
    assert manager.calls == [("reload",), ("enable_now", UNIT_NAME, "True")]


def test_install_again_replaces_the_unit(tmp_path):
    install("old\n", tmp_path, FakeServiceManager())
    install("new\n", tmp_path, FakeServiceManager())
    assert (tmp_path / UNIT_NAME).read_text() == "new\n"


def test_uninstall_stops_removes_and_reloads(tmp_path):
    install("[Unit]\n", tmp_path, FakeServiceManager())
    manager = FakeServiceManager()
    assert uninstall(tmp_path, manager) is True
    assert not (tmp_path / UNIT_NAME).exists()
    assert manager.calls == [("disable_now", UNIT_NAME), ("reload",)]


def test_uninstall_when_not_installed_does_nothing(tmp_path):
    manager = FakeServiceManager()
    assert uninstall(tmp_path, manager) is False
    assert manager.calls == []


def test_folders_follow_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert unit_folder() == tmp_path / "systemd" / "user"
    assert secrets_file() == tmp_path / "catpoop" / "service.env"


def test_folders_default_to_dot_config(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert unit_folder() == tmp_path / ".config" / "systemd" / "user"
