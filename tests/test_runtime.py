import unittest

from minecraft_manager.runtime import EventRuntime


class FakeService:
    def players(self):
        return [{"name": "Nicole"}, {"name": "VonCrush"}]


class RuntimeParserTest(unittest.TestCase):
    def test_frames_multiple_and_partial_lines_from_docker_chunks(self) -> None:
        chunks = [b"first line\nsecond", b" line\r\nthird line"]
        self.assertEqual(list(EventRuntime._decoded_log_lines(chunks)), ["first line", "second line", "third line"])

    def setUp(self) -> None:
        self.runtime = object.__new__(EventRuntime)
        self.runtime.service = FakeService()

    def test_recognizes_known_player_death(self) -> None:
        self.assertEqual(
            self.runtime._parse_death("[2026 INFO] Nicole was slain by Zombie"),
            ("Nicole", "was slain by Zombie"),
        )

    def test_ignores_chat_and_unknown_players(self) -> None:
        self.assertIsNone(self.runtime._parse_death("[INFO] Nicole says hello"))
        self.assertIsNone(self.runtime._parse_death("[INFO] Alex was slain by Zombie"))
