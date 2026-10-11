"""The systemd unit file text for the watcher service, made from `ServiceSettings`."""

import re

from catpoop.service.settings import ServiceSettings

UNIT_NAME = "catpoop.service"
_PLAIN = re.compile(r"[^\s\"'\\;]+")


def exec_start(settings: ServiceSettings) -> list[str]:
    """The command the service runs: `catpoop watch` through uv, and `op run` if set."""
    uv_run = [str(settings.uv), "run", "--frozen", "--extra", settings.runtime]
    for extra in settings.extras:
        uv_run += ["--extra", extra]
    watch = ["catpoop", "watch"]
    if settings.env_file is None:
        return [*uv_run, *watch]
    if settings.op is None:
        return [*uv_run, "--env-file", str(settings.env_file), *watch]
    return [str(settings.op), "run", f"--env-file={settings.env_file}", "--", *uv_run, *watch]


def render_unit(settings: ServiceSettings) -> str:
    """The whole unit file."""
    command = " ".join(_exec_word(word) for word in exec_start(settings))
    environment = (
        f"EnvironmentFile=-{_specifiers(str(settings.secrets_file))}\n"
        if settings.secrets_file
        else ""
    )
    return (
        "# Made by `make install` from this checkout; `make uninstall` removes it.\n"
        "[Unit]\n"
        "Description=Cat poop detector: the live watcher (catpoop watch)\n"
        "StartLimitIntervalSec=600\n"
        "StartLimitBurst=5\n"
        "\n"
        "[Service]\n"
        "Type=exec\n"
        f"WorkingDirectory={_specifiers(str(settings.checkout))}\n"
        f"{environment}"
        "Environment=PYTHONUNBUFFERED=1\n"
        f"ExecStart={command}\n"
        "Restart=on-failure\n"
        "RestartSec=30\n"
        "KillSignal=SIGINT\n"
        "TimeoutStopSec=30\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def _specifiers(text: str) -> str:
    """Stop systemd reading `%` as a specifier."""
    return text.replace("%", "%%")


def _exec_word(word: str) -> str:
    """One ExecStart word, escaped for specifiers and `$` and quoted if needed."""
    word = _specifiers(word).replace("$", "$$")
    if _PLAIN.fullmatch(word):
        return word
    return '"' + word.replace("\\", "\\\\").replace('"', '\\"') + '"'
