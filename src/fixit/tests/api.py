from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from fixit.api import validate_config


class ValidateTest(TestCase):
    maxDiff = None

    def test_validate_config(self) -> None:
        with self.subTest("validate-config valid"):
            with TemporaryDirectory() as td:
                tdp = Path(td).resolve()
                path = tdp / ".fixit.toml"
                path.write_text(
                    """
                    [tool.fixit]
                    disable = ["fixit.rules"]
                    root = true
                    """
                )

                results = validate_config(path)

                self.assertEqual(results, [])

        with self.subTest("validate-config invalid config"):
            with TemporaryDirectory() as td:
                tdp = Path(td).resolve()
                path = tdp / ".fixit.toml"
                path.write_text(
                    """
                    [tool.fixit]
                    enable = ["fixit/rules:DeprecatedABCImport"]
                    disable = ["fixit.rules"]
                    root = true
                    """
                )

                results = validate_config(path)

                self.assertEqual(
                    results,
                    [
                        "Failed to parse rule `fixit/rules:DeprecatedABCImport` for global enable: ConfigError: invalid rule name 'fixit/rules:DeprecatedABCImport'"
                    ],
                )

        with self.subTest("validate-config multiple errors"):
            with TemporaryDirectory() as td:
                tdp = Path(td).resolve()
                config = tdp / ".fixit.toml"
                config.write_text(
                    """
                    [tool.fixit]
                    enable = ["fixit/rules:DeprecatedABCImport"]
                    disable = ["fixit.rules"]
                    root = true

                    [[tool.fixit.overrides]]
                    path = "SUPER_REAL_PATH"
                    enable = ["fixit.rules:DeprecatedABCImport_SUPER_REAL"]
                    """
                )

                path = tdp / "file.py"
                path.write_text("error")

                results = validate_config(path)

                self.assertEqual(
                    results,
                    [
                        "Failed to parse rule `fixit/rules:DeprecatedABCImport` for global enable: ConfigError: invalid rule name 'fixit/rules:DeprecatedABCImport'",
                        "Failed to import rule `fixit.rules:DeprecatedABCImport_SUPER_REAL` for override enable: `SUPER_REAL_PATH`: CollectionError: could not find rule fixit.rules:DeprecatedABCImport_SUPER_REAL",
                    ],
                )
