import ast
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class EntryPointCompatibilityTests(unittest.TestCase):
    def test_root_listener_wrapper_delegates_to_package_cli(self):
        tree = ast.parse((REPO_ROOT / "listen.py").read_text(encoding="utf-8"))

        imports_cli_main = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "rl_statsapi_listener.cli"
            and any(alias.name == "main" for alias in node.names)
            for node in tree.body
        )
        guarded_main_call = any(
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            and any(
                isinstance(comparator, ast.Constant) and comparator.value == "__main__"
                for comparator in node.test.comparators
            )
            and any(
                isinstance(child, ast.Expr)
                and isinstance(child.value, ast.Call)
                and isinstance(child.value.func, ast.Name)
                and child.value.func.id == "main"
                for child in node.body
            )
            for node in tree.body
        )

        self.assertTrue(imports_cli_main)
        self.assertTrue(guarded_main_call)

    def test_console_script_delegates_to_same_package_cli(self):
        pyproject = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )

        self.assertEqual(
            pyproject["project"]["scripts"]["rl-statsapi-listen"],
            "rl_statsapi_listener.cli:main",
        )

    def test_root_obs_wrapper_reexports_canonical_obs_script(self):
        tree = ast.parse(
            (REPO_ROOT / "obs_rl_statsapi.py").read_text(encoding="utf-8")
        )

        reexports_canonical_script = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "integrations.obs.obs_rl_statsapi"
            and any(alias.name == "*" for alias in node.names)
            for node in tree.body
        )

        self.assertTrue(reexports_canonical_script)


if __name__ == "__main__":
    unittest.main()
