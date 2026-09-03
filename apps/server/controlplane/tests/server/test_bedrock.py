import pytest

from src.server.console import BedrockClient


# ---------------------------------------------------------------------------
# BedrockParserTest
# ---------------------------------------------------------------------------

def test_parses_gamerule_values() -> None:
    logs = "showcoordinates = true\nspawnradius = 5\n"
    assert BedrockClient.parse_gamerules(logs, ["showcoordinates", "spawnradius"]) == {
        "showcoordinates": "true", "spawnradius": "5",
    }


def test_uses_connection_history_when_list_output_is_unavailable() -> None:
    history = "\n".join([
        "Player connected: Nicole, xuid: 1",
        "Player connected: Don, xuid: 2",
        "Player disconnected: Don, xuid: 2",
    ])
    players, online, maximum = BedrockClient.parse_players("", history)
    assert players == ["Nicole"]
    assert online == 1
    assert maximum == 0


def test_trusts_an_explicit_empty_server_list() -> None:
    history = "Player connected: Nicole, xuid: 1"
    players, online, maximum = BedrockClient.parse_players("There are 0/10 players online:", history)
    assert players == []
    assert online == 0
    assert maximum == 10


def test_extracts_player_xuids_from_connection_history() -> None:
    history = "Player connected: VonCrush, xuid: 2535000000000001"
    assert BedrockClient.parse_xuids(history) == {"VonCrush": "2535000000000001"}


# ---------------------------------------------------------------------------
# ParseGameruleTest
# ---------------------------------------------------------------------------

def test_returns_empty_dict_when_no_rules_match() -> None:
    assert BedrockClient.parse_gamerules("unrelated log output", ["keepInventory"]) == {}


def test_returns_empty_dict_for_empty_rule_list() -> None:
    assert BedrockClient.parse_gamerules("keepInventory = true", []) == {}


def test_uses_last_match_when_rule_appears_multiple_times() -> None:
    logs = "keepInventory = false\nkeepInventory = true\n"
    assert BedrockClient.parse_gamerules(logs, ["keepInventory"]) == {"keepInventory": "true"}


def test_parses_integer_gamerule() -> None:
    logs = "spawnradius = 10\n"
    assert BedrockClient.parse_gamerules(logs, ["spawnradius"]) == {"spawnradius": "10"}


def test_is_case_insensitive_for_boolean_values() -> None:
    logs = "keepInventory = TRUE\n"
    assert BedrockClient.parse_gamerules(logs, ["keepInventory"]) == {"keepInventory": "true"}


def test_skips_rules_not_present_in_logs() -> None:
    logs = "showcoordinates = true\n"
    result = BedrockClient.parse_gamerules(logs, ["showcoordinates", "keepInventory"])
    assert "showcoordinates" in result
    assert "keepInventory" not in result


# ---------------------------------------------------------------------------
# ParsePlayersTest
# ---------------------------------------------------------------------------

def test_parses_players_from_list_output() -> None:
    logs = "There are 2/10 players online:\nVonCrush, Nicole\n"
    players, online, maximum = BedrockClient.parse_players(logs, "")
    assert "VonCrush" in players
    assert "Nicole" in players
    assert online == 2
    assert maximum == 10


def test_parses_single_player_from_list_output() -> None:
    logs = "There are 1/20 players online:\nVonCrush\n"
    players, online, maximum = BedrockClient.parse_players(logs, "")
    assert players == ["VonCrush"]
    assert online == 1
    assert maximum == 20


def test_filters_out_log_noise_after_list_marker() -> None:
    logs = (
        "There are 1/10 players online:\n"
        "[INFO] some gamerule output\n"
        "VonCrush\n"
    )
    players, _, _ = BedrockClient.parse_players(logs, "")
    assert players == ["VonCrush"]


def test_uses_last_list_marker_when_multiple_present() -> None:
    logs = (
        "There are 1/10 players online:\nOldPlayer\n"
        "There are 1/10 players online:\nVonCrush\n"
    )
    players, _, _ = BedrockClient.parse_players(logs, "")
    assert players == ["VonCrush"]


def test_returns_empty_when_logs_and_history_are_empty() -> None:
    players, online, maximum = BedrockClient.parse_players("", "")
    assert players == []
    assert online == 0
    assert maximum == 0


def test_history_connect_disconnect_is_case_insensitive() -> None:
    history = (
        "PLAYER CONNECTED: VonCrush, XUID: 1\n"
        "PLAYER DISCONNECTED: VonCrush, XUID: 1\n"
    )
    players, online, _ = BedrockClient.parse_players("", history)
    assert players == []
    assert online == 0


def test_history_tracks_multiple_connect_disconnect_cycles() -> None:
    history = (
        "Player connected: Alpha, xuid: 1\n"
        "Player connected: Beta, xuid: 2\n"
        "Player disconnected: Alpha, xuid: 1\n"
    )
    players, online, _ = BedrockClient.parse_players("", history)
    assert players == ["Beta"]
    assert online == 1


def test_reconnecting_player_remains_online() -> None:
    history = (
        "Player connected: VonCrush, xuid: 1\n"
        "Player disconnected: VonCrush, xuid: 1\n"
        "Player connected: VonCrush, xuid: 1\n"
    )
    players, _, _ = BedrockClient.parse_players("", history)
    assert players == ["VonCrush"]


def test_limits_players_to_online_count_from_list() -> None:
    logs = "There are 1/10 players online:\nVonCrush, Nicole\n"
    players, online, _ = BedrockClient.parse_players(logs, "")
    assert online == 1
    assert len(players) == 1


# ---------------------------------------------------------------------------
# ParseXuidsTest
# ---------------------------------------------------------------------------

def test_returns_empty_dict_for_empty_history() -> None:
    assert BedrockClient.parse_xuids("") == {}


def test_extracts_multiple_xuids() -> None:
    history = (
        "Player connected: VonCrush, xuid: 2535000000000001\n"
        "Player connected: Nicole, xuid: 2535000000000002\n"
    )
    result = BedrockClient.parse_xuids(history)
    assert result["VonCrush"] == "2535000000000001"
    assert result["Nicole"] == "2535000000000002"


def test_last_xuid_wins_for_repeated_player() -> None:
    history = (
        "Player connected: VonCrush, xuid: 111\n"
        "Player connected: VonCrush, xuid: 222\n"
    )
    result = BedrockClient.parse_xuids(history)
    assert result["VonCrush"] == "222"


def test_ignores_disconnect_lines() -> None:
    history = "Player disconnected: VonCrush, xuid: 2535000000000001\n"
    assert BedrockClient.parse_xuids(history) == {}


def test_is_case_insensitive_for_keyword() -> None:
    history = "PLAYER CONNECTED: VonCrush, XUID: 2535000000000001\n"
    result = BedrockClient.parse_xuids(history)
    assert result.get("VonCrush") == "2535000000000001"


def test_strips_whitespace_from_name_and_xuid() -> None:
    history = "Player connected:  VonCrush , xuid:  2535000000000001 \n"
    result = BedrockClient.parse_xuids(history)
    assert "VonCrush" in result
    assert result["VonCrush"] == "2535000000000001"


# ---------------------------------------------------------------------------
# BedrockClientValidationTest
# ---------------------------------------------------------------------------

@pytest.fixture
def bedrock_client() -> BedrockClient:
    return BedrockClient("mc", ["keepInventory"])


def test_send_rejects_empty_command(bedrock_client: BedrockClient) -> None:
    with pytest.raises(ValueError):
        bedrock_client.send([])


def test_send_rejects_command_with_special_chars(bedrock_client: BedrockClient) -> None:
    with pytest.raises(ValueError):
        bedrock_client.send(["say", "hello world"])


def test_send_and_read_rejects_empty_command(bedrock_client: BedrockClient) -> None:
    with pytest.raises(ValueError):
        bedrock_client.send_and_read([])


def test_send_and_read_rejects_command_with_special_chars(bedrock_client: BedrockClient) -> None:
    with pytest.raises(ValueError):
        bedrock_client.send_and_read(["rm; malicious"])


def test_set_operator_rejects_empty_player(bedrock_client: BedrockClient) -> None:
    with pytest.raises(ValueError):
        bedrock_client.set_operator("", True)


def test_set_operator_rejects_player_name_too_long(bedrock_client: BedrockClient) -> None:
    with pytest.raises(ValueError):
        bedrock_client.set_operator("a" * 33, True)


def test_set_operator_rejects_player_with_semicolon(bedrock_client: BedrockClient) -> None:
    with pytest.raises(ValueError):
        bedrock_client.set_operator("Von;Crush", True)
