from catpoop.alexa_skill.tunnel import tunnel_setup
from catpoop.cli import main
from catpoop.config import AlexaSkillSettings


def test_cloudflare_routes_only_alexa_to_the_endpoint_and_404s_the_rest():
    text = tunnel_setup(AlexaSkillSettings(port=9000, hostname="litter.example.com"))
    assert "hostname: litter.example.com" in text
    assert "path: ^/alexa$" in text
    assert "service: http://127.0.0.1:9000" in text
    assert "service: http_status:404" in text
    assert "https://litter.example.com/alexa" in text


def test_cloudflare_without_a_hostname_shows_a_placeholder():
    text = tunnel_setup(AlexaSkillSettings())
    assert "litter.example.com" in text
    assert "[alexa_skill] hostname" in text


def test_tailscale_funnels_only_alexa():
    text = tunnel_setup(AlexaSkillSettings(tunnel="tailscale", port=9000))
    assert "tailscale funnel --bg --set-path=/alexa http://127.0.0.1:9000/alexa" in text
    assert "cloudflared" not in text


def test_tailscale_warns_that_funnel_opens_everything_already_served_on_443():
    text = tunnel_setup(AlexaSkillSettings(tunnel="tailscale"))
    check, funnel = text.index("tailscale serve status"), text.index("tailscale funnel --bg")
    assert check < funnel
    assert "WARNING" in text


def test_a_host_of_all_addresses_is_reached_on_localhost():
    text = tunnel_setup(AlexaSkillSettings(tunnel="tailscale", host="0.0.0.0"))
    assert "http://127.0.0.1:8767/alexa" in text


def test_the_command_prints_the_setup_for_the_configured_tunnel(tmp_path, capsys):
    config = tmp_path / "config.toml"
    config.write_text(
        '[parts]\ncamera = "a"\ndetector = "a"\nevent_rules = "a"\nevent_log = "a"\n'
        'presence = "a"\ncommunications = "a"\n[paths]\nprivate_data_store = "/x"\n'
        '[alexa_skill]\ntunnel = "tailscale"\n'
    )
    assert main(["alexa-tunnel", "--config", str(config)]) == 0
    assert "tailscale funnel" in capsys.readouterr().out


def test_the_command_reports_a_bad_config(tmp_path, capsys):
    assert main(["alexa-tunnel", "--config", str(tmp_path / "missing.toml")]) == 1
    assert "not found" in capsys.readouterr().err


def test_cloudflare_also_routes_the_smart_home_path_when_it_is_on():
    settings = AlexaSkillSettings(enabled=True, hostname="litter.example.com", smart_home=True)
    assert "path: ^/alexa(/smart-home)?$" in tunnel_setup(settings)
