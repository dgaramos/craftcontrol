import unittest

from minecraft_manager.bedrock import BedrockClient


class BedrockParserTest(unittest.TestCase):
    def test_parses_gamerule_values(self) -> None:
        logs = "showcoordinates = true\nspawnradius = 5\n"
        self.assertEqual(
            BedrockClient.parse_gamerules(logs, ["showcoordinates", "spawnradius"]),
            {"showcoordinates": "true", "spawnradius": "5"},
        )

    def test_uses_connection_history_when_list_output_is_unavailable(self) -> None:
        history = "\n".join([
            "Player connected: Nicole, xuid: 1",
            "Player connected: Don, xuid: 2",
            "Player disconnected: Don, xuid: 2",
        ])
        players, online, maximum = BedrockClient.parse_players("", history)
        self.assertEqual(players, ["Nicole"])
        self.assertEqual(online, 1)
        self.assertEqual(maximum, 0)

    def test_trusts_an_explicit_empty_server_list(self) -> None:
        history = "Player connected: Nicole, xuid: 1"
        players, online, maximum = BedrockClient.parse_players("There are 0/10 players online:", history)
        self.assertEqual(players, [])
        self.assertEqual(online, 0)
        self.assertEqual(maximum, 10)

    def test_extracts_player_xuids_from_connection_history(self) -> None:
        history = "Player connected: VonCrush, xuid: 2535000000000001"
        self.assertEqual(BedrockClient.parse_xuids(history), {"VonCrush": "2535000000000001"})


class ParseGameruleTest(unittest.TestCase):
    def test_returns_empty_dict_when_no_rules_match(self) -> None:
        self.assertEqual(BedrockClient.parse_gamerules("unrelated log output", ["keepInventory"]), {})

    def test_returns_empty_dict_for_empty_rule_list(self) -> None:
        self.assertEqual(BedrockClient.parse_gamerules("keepInventory = true", []), {})

    def test_uses_last_match_when_rule_appears_multiple_times(self) -> None:
        logs = "keepInventory = false\nkeepInventory = true\n"
        self.assertEqual(BedrockClient.parse_gamerules(logs, ["keepInventory"]), {"keepInventory": "true"})

    def test_parses_integer_gamerule(self) -> None:
        logs = "spawnradius = 10\n"
        self.assertEqual(BedrockClient.parse_gamerules(logs, ["spawnradius"]), {"spawnradius": "10"})

    def test_is_case_insensitive_for_boolean_values(self) -> None:
        logs = "keepInventory = TRUE\n"
        self.assertEqual(BedrockClient.parse_gamerules(logs, ["keepInventory"]), {"keepInventory": "true"})

    def test_skips_rules_not_present_in_logs(self) -> None:
        logs = "showcoordinates = true\n"
        result = BedrockClient.parse_gamerules(logs, ["showcoordinates", "keepInventory"])
        self.assertIn("showcoordinates", result)
        self.assertNotIn("keepInventory", result)


class ParsePlayersTest(unittest.TestCase):
    def test_parses_players_from_list_output(self) -> None:
        logs = "There are 2/10 players online:\nVonCrush, Nicole\n"
        players, online, maximum = BedrockClient.parse_players(logs, "")
        self.assertIn("VonCrush", players)
        self.assertIn("Nicole", players)
        self.assertEqual(online, 2)
        self.assertEqual(maximum, 10)

    def test_parses_single_player_from_list_output(self) -> None:
        logs = "There are 1/20 players online:\nVonCrush\n"
        players, online, maximum = BedrockClient.parse_players(logs, "")
        self.assertEqual(players, ["VonCrush"])
        self.assertEqual(online, 1)
        self.assertEqual(maximum, 20)

    def test_filters_out_log_noise_after_list_marker(self) -> None:
        logs = (
            "There are 1/10 players online:\n"
            "[INFO] some gamerule output\n"
            "VonCrush\n"
        )
        players, online, _ = BedrockClient.parse_players(logs, "")
        self.assertEqual(players, ["VonCrush"])

    def test_uses_last_list_marker_when_multiple_present(self) -> None:
        logs = (
            "There are 1/10 players online:\nOldPlayer\n"
            "There are 1/10 players online:\nVonCrush\n"
        )
        players, online, _ = BedrockClient.parse_players(logs, "")
        self.assertEqual(players, ["VonCrush"])

    def test_returns_empty_when_logs_and_history_are_empty(self) -> None:
        players, online, maximum = BedrockClient.parse_players("", "")
        self.assertEqual(players, [])
        self.assertEqual(online, 0)
        self.assertEqual(maximum, 0)

    def test_history_connect_disconnect_is_case_insensitive(self) -> None:
        history = (
            "PLAYER CONNECTED: VonCrush, XUID: 1\n"
            "PLAYER DISCONNECTED: VonCrush, XUID: 1\n"
        )
        players, online, _ = BedrockClient.parse_players("", history)
        self.assertEqual(players, [])
        self.assertEqual(online, 0)

    def test_history_tracks_multiple_connect_disconnect_cycles(self) -> None:
        history = (
            "Player connected: Alpha, xuid: 1\n"
            "Player connected: Beta, xuid: 2\n"
            "Player disconnected: Alpha, xuid: 1\n"
        )
        players, online, _ = BedrockClient.parse_players("", history)
        self.assertEqual(players, ["Beta"])
        self.assertEqual(online, 1)

    def test_reconnecting_player_remains_online(self) -> None:
        history = (
            "Player connected: VonCrush, xuid: 1\n"
            "Player disconnected: VonCrush, xuid: 1\n"
            "Player connected: VonCrush, xuid: 1\n"
        )
        players, online, _ = BedrockClient.parse_players("", history)
        self.assertEqual(players, ["VonCrush"])

    def test_limits_players_to_online_count_from_list(self) -> None:
        # server reports 1 online but log has two names — trust the count
        logs = "There are 1/10 players online:\nVonCrush, Nicole\n"
        players, online, _ = BedrockClient.parse_players(logs, "")
        self.assertEqual(online, 1)
        self.assertEqual(len(players), 1)


class ParseXuidsTest(unittest.TestCase):
    def test_returns_empty_dict_for_empty_history(self) -> None:
        self.assertEqual(BedrockClient.parse_xuids(""), {})

    def test_extracts_multiple_xuids(self) -> None:
        history = (
            "Player connected: VonCrush, xuid: 2535000000000001\n"
            "Player connected: Nicole, xuid: 2535000000000002\n"
        )
        result = BedrockClient.parse_xuids(history)
        self.assertEqual(result["VonCrush"], "2535000000000001")
        self.assertEqual(result["Nicole"], "2535000000000002")

    def test_last_xuid_wins_for_repeated_player(self) -> None:
        history = (
            "Player connected: VonCrush, xuid: 111\n"
            "Player connected: VonCrush, xuid: 222\n"
        )
        result = BedrockClient.parse_xuids(history)
        self.assertEqual(result["VonCrush"], "222")

    def test_ignores_disconnect_lines(self) -> None:
        history = "Player disconnected: VonCrush, xuid: 2535000000000001\n"
        self.assertEqual(BedrockClient.parse_xuids(history), {})

    def test_is_case_insensitive_for_keyword(self) -> None:
        history = "PLAYER CONNECTED: VonCrush, XUID: 2535000000000001\n"
        result = BedrockClient.parse_xuids(history)
        self.assertEqual(result.get("VonCrush"), "2535000000000001")

    def test_strips_whitespace_from_name_and_xuid(self) -> None:
        history = "Player connected:  VonCrush , xuid:  2535000000000001 \n"
        result = BedrockClient.parse_xuids(history)
        self.assertIn("VonCrush", result)
        self.assertEqual(result["VonCrush"], "2535000000000001")


class BedrockClientValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = BedrockClient("mc", ["keepInventory"])

    def test_send_rejects_empty_command(self) -> None:
        with self.assertRaises(ValueError):
            self.client.send([])

    def test_send_rejects_command_with_special_chars(self) -> None:
        with self.assertRaises(ValueError):
            self.client.send(["say", "hello world"])

    def test_send_and_read_rejects_empty_command(self) -> None:
        with self.assertRaises(ValueError):
            self.client.send_and_read([])

    def test_send_and_read_rejects_command_with_special_chars(self) -> None:
        with self.assertRaises(ValueError):
            self.client.send_and_read(["rm; malicious"])

    def test_set_operator_rejects_empty_player(self) -> None:
        with self.assertRaises(ValueError):
            self.client.set_operator("", True)

    def test_set_operator_rejects_player_name_too_long(self) -> None:
        with self.assertRaises(ValueError):
            self.client.set_operator("a" * 33, True)

    def test_set_operator_rejects_player_with_semicolon(self) -> None:
        with self.assertRaises(ValueError):
            self.client.set_operator("Von;Crush", True)
