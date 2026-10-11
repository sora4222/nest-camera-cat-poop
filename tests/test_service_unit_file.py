from pathlib import Path

from catpoop.service.settings import ServiceSettings
from catpoop.service.unit_file import exec_start, render_unit

CHECKOUT = Path("/srv/checkout")
UV = Path("/opt/bin/uv")
OP = Path("/opt/bin/op")


def _line(unit: str, key: str) -> str:
    return next(line for line in unit.splitlines() if line.startswith(f"{key}="))


def test_runs_the_watcher_from_the_checkout_with_the_chosen_extras():
    settings = ServiceSettings(checkout=CHECKOUT, uv=UV, runtime="nvidia", extras=("google",))
    assert exec_start(settings) == [
        "/opt/bin/uv", "run", "--frozen", "--extra", "nvidia", "--extra", "google",
        "catpoop", "watch",
    ]  # fmt: skip
    unit = render_unit(settings)
    assert _line(unit, "WorkingDirectory") == "WorkingDirectory=/srv/checkout"
    assert _line(unit, "ExecStart").startswith("ExecStart=/opt/bin/uv run --frozen")


def test_reads_a_plain_env_file_with_uv_when_there_is_no_op():
    settings = ServiceSettings(checkout=CHECKOUT, uv=UV, env_file=CHECKOUT / ".env")
    assert exec_start(settings) == [
        "/opt/bin/uv", "run", "--frozen", "--extra", "cpu", "--env-file", "/srv/checkout/.env",
        "catpoop", "watch",
    ]  # fmt: skip


def test_fills_in_1password_references_with_op_run():
    settings = ServiceSettings(checkout=CHECKOUT, uv=UV, env_file=CHECKOUT / ".env", op=OP)
    assert exec_start(settings) == [
        "/opt/bin/op", "run", "--env-file=/srv/checkout/.env", "--",
        "/opt/bin/uv", "run", "--frozen", "--extra", "cpu", "catpoop", "watch",
    ]  # fmt: skip


def test_op_is_not_used_without_an_env_file():
    settings = ServiceSettings(checkout=CHECKOUT, uv=UV, op=OP)
    assert exec_start(settings)[0] == "/opt/bin/uv"


def test_service_secrets_file_is_optional():
    secrets = Path("/home/u/.config/catpoop/service.env")
    unit = render_unit(ServiceSettings(checkout=CHECKOUT, uv=UV, secrets_file=secrets))
    assert _line(unit, "EnvironmentFile") == f"EnvironmentFile=-{secrets}"
    assert "EnvironmentFile" not in render_unit(ServiceSettings(checkout=CHECKOUT, uv=UV))


def test_restarts_on_failure_stops_like_ctrl_c_and_starts_with_the_user():
    unit = render_unit(ServiceSettings(checkout=CHECKOUT, uv=UV))
    assert "Restart=on-failure" in unit
    assert "KillSignal=SIGINT" in unit
    assert "WantedBy=default.target" in unit


def test_quotes_and_escapes_awkward_paths():
    checkout = Path("/home/u/my cats/100%")
    settings = ServiceSettings(checkout=checkout, uv=UV, env_file=checkout / ".env")
    unit = render_unit(settings)
    assert _line(unit, "WorkingDirectory") == "WorkingDirectory=/home/u/my cats/100%%"
    assert '--env-file "/home/u/my cats/100%%/.env"' in _line(unit, "ExecStart")


def test_dollar_signs_in_exec_start_are_not_expanded_by_systemd():
    settings = ServiceSettings(checkout=CHECKOUT, uv=Path("/srv/$HOME/uv"))
    assert _line(render_unit(settings), "ExecStart").startswith("ExecStart=/srv/$$HOME/uv run")
