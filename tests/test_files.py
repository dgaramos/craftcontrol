import tempfile
import unittest
from pathlib import Path

from minecraft_manager.files import ServerFiles


class ServerFilesTest(unittest.TestCase):
    def test_updates_env_without_losing_comments_or_unrelated_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_file = root / ".env"
            env_file.write_text("# Server\nSERVER_NAME=Old\nMAX_PLAYERS=4\n", encoding="utf-8")
            files = ServerFiles(env_file, root / "server.properties")

            files.write_env({"SERVER_NAME": "MalavaziRamos", "DIFFICULTY": "normal"})

            self.assertEqual(
                env_file.read_text(encoding="utf-8"),
                "# Server\nSERVER_NAME=MalavaziRamos\nMAX_PLAYERS=4\nDIFFICULTY=normal\n",
            )

    def test_reads_bedrock_player_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            permissions = root / "permissions.json"
            permissions.write_text('[{"permission":"operator","xuid":"123"}]', encoding="utf-8")
            files = ServerFiles(root / ".env", root / "server.properties", permissions)
            self.assertEqual(files.read_permissions(), [{"permission": "operator", "xuid": "123"}])
