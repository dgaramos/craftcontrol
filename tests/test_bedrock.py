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
