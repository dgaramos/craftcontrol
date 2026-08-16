import pytest

from minecraft_manager.schema import GAMERULES, SETTINGS, validate_value


def test_normalizes_boolean_values() -> None:
    assert validate_value(SETTINGS["ALLOW_CHEATS"], True) == "true"
    assert validate_value(SETTINGS["ALLOW_CHEATS"], "false") == "false"


def test_rejects_out_of_range_number() -> None:
    with pytest.raises(ValueError, match="fora do intervalo"):
        validate_value(SETTINGS["MAX_PLAYERS"], 101)


def test_rejects_unknown_select_option() -> None:
    with pytest.raises(ValueError, match="opção inválida"):
        validate_value(SETTINGS["DIFFICULTY"], "nightmare")


def test_rejects_multiline_text() -> None:
    with pytest.raises(ValueError, match="texto inválido"):
        validate_value(SETTINGS["SERVER_NAME"], "server\nINJECTED=true")


def test_every_field_has_bilingual_help_text() -> None:
    for definition in [*SETTINGS.values(), *GAMERULES.values()]:
        assert definition.get("label")
        assert definition.get("description")
        assert definition.get("label_en")
        assert definition.get("description_en")
