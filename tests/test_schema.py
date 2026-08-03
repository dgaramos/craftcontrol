import unittest

from minecraft_manager.schema import SETTINGS, validate_value


class ValidateValueTest(unittest.TestCase):
    def test_normalizes_boolean_values(self) -> None:
        self.assertEqual(validate_value(SETTINGS["ALLOW_CHEATS"], True), "true")
        self.assertEqual(validate_value(SETTINGS["ALLOW_CHEATS"], "false"), "false")

    def test_rejects_out_of_range_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "fora do intervalo"):
            validate_value(SETTINGS["MAX_PLAYERS"], 101)

    def test_rejects_unknown_select_option(self) -> None:
        with self.assertRaisesRegex(ValueError, "opção inválida"):
            validate_value(SETTINGS["DIFFICULTY"], "nightmare")

    def test_rejects_multiline_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "texto inválido"):
            validate_value(SETTINGS["SERVER_NAME"], "server\nINJECTED=true")
