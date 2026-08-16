import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULES = (
    "src/main.py",
    "src/asr/sensevoice_backend.py",
    "src/audio/recorder.py",
    "src/audio/vad_recorder.py",
    "src/wakeword/detector.py",
    "src/core/state_manager.py",
    "src/llm/client.py",
)


class PresentationOutputBoundaryTests(unittest.TestCase):
    def test_runtime_modules_do_not_call_print_directly(self):
        violations = []
        for relative_path in RUNTIME_MODULES:
            path = PROJECT_ROOT / relative_path
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "print"
                ):
                    violations.append(f"{relative_path}:{node.lineno}")

        self.assertEqual(
            violations,
            [],
            "生产运行路径不得直接 print，应使用 PRESENT 或 logging："
            + ", ".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
