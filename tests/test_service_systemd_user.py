import subprocess

import pytest

from catpoop.service.settings import ServiceSetupError
from catpoop.service.systemd_user import SystemdUser


def test_runs_systemctl_for_the_user():
    ran: list[list[str]] = []
    manager = SystemdUser(runner=lambda argv: ran.append(list(argv)))
    manager.reload()
    manager.enable_and_restart("catpoop.service")
    manager.disable_now("catpoop.service")
    assert ran == [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "catpoop.service"],
        ["systemctl", "--user", "restart", "catpoop.service"],
        ["systemctl", "--user", "disable", "--now", "catpoop.service"],
    ]


def test_failures_are_readable():
    def fail(argv):
        raise subprocess.CalledProcessError(1, argv)

    with pytest.raises(ServiceSetupError, match="daemon-reload"):
        SystemdUser(runner=fail).reload()


def test_no_systemctl():
    def missing(argv):
        raise FileNotFoundError(argv[0])

    with pytest.raises(ServiceSetupError, match="systemd"):
        SystemdUser(runner=missing).reload()
