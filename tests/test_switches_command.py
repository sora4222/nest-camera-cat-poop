from datetime import UTC, datetime, timedelta

import pytest
from fake_clock import FakeClock

from catpoop.cli import main
from catpoop.communications.command import parse_duration, run_dnd, run_pee
from catpoop.communications.switches import Switches
from catpoop.domain import Urgency

NOW = datetime(2026, 6, 1, 20, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2h", timedelta(hours=2)),
        ("30m", timedelta(minutes=30)),
        ("1h30m", timedelta(hours=1, minutes=30)),
        ("90s", timedelta(seconds=90)),
        ("1d", timedelta(days=1)),
    ],
)
def test_durations(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "2", "h", "2x", "-2h", "0m"])
def test_bad_durations(text):
    with pytest.raises(ValueError):
        parse_duration(text)


def test_dnd_for_a_while_then_off(tmp_path, capsys):
    switches = Switches(tmp_path / "switches.json")
    clock = FakeClock(NOW)
    assert run_dnd(switches, clock, duration="2h") == 0
    dnd = switches.do_not_disturb(NOW)
    assert dnd is not None and dnd.until == NOW + timedelta(hours=2) and dnd.allow is None
    assert "Do Not Disturb until" in capsys.readouterr().out
    assert run_dnd(switches, clock, off=True) == 0
    assert switches.do_not_disturb(NOW) is None
    assert "off" in capsys.readouterr().out


def test_dnd_can_say_which_urgencies_get_through(tmp_path):
    switches = Switches(tmp_path / "switches.json")
    run_dnd(switches, FakeClock(NOW), duration="1h", allow=["none"])
    dnd = switches.do_not_disturb(NOW)
    assert dnd is not None and dnd.allow == ()
    run_dnd(switches, FakeClock(NOW), duration="1h", allow=["normal", "urgent"])
    dnd = switches.do_not_disturb(NOW)
    assert dnd is not None and dnd.allow == (Urgency.NORMAL, Urgency.URGENT)


def test_dnd_with_nothing_says_whether_it_is_on(tmp_path, capsys):
    switches = Switches(tmp_path / "switches.json")
    assert run_dnd(switches, FakeClock(NOW)) == 0
    assert "off" in capsys.readouterr().out


def test_dnd_rejects_a_bad_duration(tmp_path, capsys):
    switches = Switches(tmp_path / "switches.json")
    assert run_dnd(switches, FakeClock(NOW), duration="soon") == 2
    assert "soon" in capsys.readouterr().err


def test_pee_announcements_on_and_off(tmp_path, capsys):
    switches = Switches(tmp_path / "switches.json")
    assert run_pee(switches, "off") == 0
    assert switches.pee_announcements() is False
    assert run_pee(switches, "on") == 0
    assert switches.pee_announcements() is True
    assert "on" in capsys.readouterr().out


def test_the_cli_uses_the_switches_in_the_state_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert main(["pee-announcements", "off"]) == 0
    assert main(["dnd", "--for", "2h", "--allow", "urgent"]) == 0
    switches = Switches.default()
    assert switches.pee_announcements() is False
    dnd = switches.do_not_disturb(datetime.now(UTC))
    assert dnd is not None and dnd.allow == (Urgency.URGENT,)
    assert main(["dnd", "--off"]) == 0
    assert switches.do_not_disturb(datetime.now(UTC)) is None


@pytest.mark.parametrize("off", [False, True])
def test_dnd_rejects_allow_without_a_duration(tmp_path, capsys, off):
    switches = Switches(tmp_path / "switches.json")
    run_dnd(switches, FakeClock(NOW), duration="1h")
    assert run_dnd(switches, FakeClock(NOW), off=off, allow=["none"]) == 2
    assert "--allow" in capsys.readouterr().err
    dnd = switches.do_not_disturb(NOW)
    assert dnd is not None and dnd.allow is None


def test_dnd_rejects_none_with_other_urgencies(tmp_path, capsys):
    switches = Switches(tmp_path / "switches.json")
    assert run_dnd(switches, FakeClock(NOW), duration="2h", allow=["none", "urgent"]) == 2
    assert "none" in capsys.readouterr().err
    assert switches.do_not_disturb(NOW) is None
