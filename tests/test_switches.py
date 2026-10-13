from datetime import UTC, datetime, timedelta

from catpoop.communications.switches import DoNotDisturb, Switches
from catpoop.domain import Urgency

NOW = datetime(2026, 6, 1, 20, 0, tzinfo=UTC)


def test_nothing_is_switched_before_anything_is_set(tmp_path):
    switches = Switches(tmp_path / "switches.json")
    assert switches.do_not_disturb(NOW) is None
    assert switches.pee_announcements() is True


def test_do_not_disturb_lasts_until_its_end_and_is_seen_by_another_reader(tmp_path):
    path = tmp_path / "state" / "switches.json"
    Switches(path).set_do_not_disturb(NOW + timedelta(hours=2))
    reader = Switches(path)
    assert reader.do_not_disturb(NOW) == DoNotDisturb(NOW + timedelta(hours=2), None)
    assert reader.do_not_disturb(NOW + timedelta(hours=2)) is None


def test_do_not_disturb_can_say_which_urgencies_get_through_and_be_switched_off(tmp_path):
    switches = Switches(tmp_path / "switches.json")
    switches.set_do_not_disturb(NOW + timedelta(hours=1), allow=[Urgency.URGENT])
    dnd = switches.do_not_disturb(NOW)
    assert dnd is not None and dnd.allow == (Urgency.URGENT,)
    switches.clear_do_not_disturb()
    assert switches.do_not_disturb(NOW) is None


def test_pee_announcements_switch_is_kept_with_do_not_disturb(tmp_path):
    path = tmp_path / "switches.json"
    Switches(path).set_do_not_disturb(NOW + timedelta(hours=1))
    Switches(path).set_pee_announcements(False)
    reader = Switches(path)
    assert reader.pee_announcements() is False
    assert reader.do_not_disturb(NOW) is not None
    reader.set_pee_announcements(True)
    assert Switches(path).pee_announcements() is True


def test_a_broken_file_counts_as_nothing_switched(tmp_path, caplog):
    path = tmp_path / "switches.json"
    path.write_text("{not json")
    switches = Switches(path)
    assert switches.do_not_disturb(NOW) is None
    assert switches.pee_announcements() is True
    assert "switches" in caplog.text
    path.write_text('{"dnd": {"until": "soon"}}')
    assert switches.do_not_disturb(NOW) is None


def test_default_file_is_in_the_users_state_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert Switches.default().path == tmp_path / "catpoop" / "switches.json"


def test_poop_and_visits_go_quiet_separately_until_their_end(tmp_path):
    path = tmp_path / "switches.json"
    Switches(path).set_quiet("poop", NOW + timedelta(hours=2))
    reader = Switches(path)
    assert reader.quiet_until("poop", NOW) == NOW + timedelta(hours=2)
    assert reader.quiet_until("visits", NOW) is None
    assert reader.quiet_until("poop", NOW + timedelta(hours=2)) is None
    reader.set_quiet("visits", NOW + timedelta(hours=1))
    reader.clear_quiet("poop")
    assert reader.quiet_until("poop", NOW) is None
    assert reader.quiet_until("visits", NOW) == NOW + timedelta(hours=1)


def test_a_broken_quiet_time_counts_as_not_quiet(tmp_path, caplog):
    path = tmp_path / "switches.json"
    path.write_text('{"quiet": {"poop": "soon"}}')
    assert Switches(path).quiet_until("poop", NOW) is None
    assert "quiet" in caplog.text
