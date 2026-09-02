from pathlib import Path

from minecraft_manager.server.files import ServerFiles


def test_updates_env_without_losing_comments_or_unrelated_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# Server\nSERVER_NAME=Old\nMAX_PLAYERS=4\n", encoding="utf-8")
    files = ServerFiles(env_file, tmp_path / "server.properties")

    files.write_env({"SERVER_NAME": "MalavaziRamos", "DIFFICULTY": "normal"})

    assert env_file.read_text(encoding="utf-8") == "# Server\nSERVER_NAME=MalavaziRamos\nMAX_PLAYERS=4\nDIFFICULTY=normal\n"


def test_updates_properties_without_losing_comments_or_unrelated_values(tmp_path: Path) -> None:
    properties_file = tmp_path / "server.properties"
    properties_file.write_text("# Server\nserver-name=Old\nmax-players=4\n", encoding="utf-8")
    files = ServerFiles(tmp_path / ".env", properties_file)

    files.write_properties({"server-name": "MalavaziRamos", "difficulty": "normal"})

    assert properties_file.read_text(encoding="utf-8") == "# Server\nserver-name=MalavaziRamos\nmax-players=4\ndifficulty=normal\n"


def test_reads_bedrock_player_permissions(tmp_path: Path) -> None:
    permissions = tmp_path / "permissions.json"
    permissions.write_text('[{"permission":"operator","xuid":"123"}]', encoding="utf-8")
    files = ServerFiles(tmp_path / ".env", tmp_path / "server.properties", permissions)
    assert files.read_permissions() == [{"permission": "operator", "xuid": "123"}]
