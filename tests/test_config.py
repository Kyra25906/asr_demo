import importlib
import os
import unittest
from unittest.mock import patch

import src.config as config_module
from src.config import validate_shadow_flags


class ValidateShadowFlagsTests(unittest.TestCase):
    def test_enabled_false_execute_false_is_valid(self):
        validate_shadow_flags(enabled=False, execute=False)

    def test_enabled_true_execute_false_is_valid(self):
        validate_shadow_flags(enabled=True, execute=False)

    def test_enabled_true_execute_true_is_valid(self):
        validate_shadow_flags(enabled=True, execute=True)

    def test_execute_true_without_enabled_is_rejected(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "UNIFIED_SHADOW_EXECUTE_ENABLED=true 要求 "
            "UNIFIED_SHADOW_ENABLED=true",
        ):
            validate_shadow_flags(enabled=False, execute=True)


class ConfigLoadFailFastTests(unittest.TestCase):
    def test_illegal_combination_fails_fast_on_load(self):
        try:
            with patch.dict(
                os.environ,
                {
                    "UNIFIED_SHADOW_ENABLED": "false",
                    "UNIFIED_SHADOW_EXECUTE_ENABLED": "true",
                },
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "UNIFIED_SHADOW_EXECUTE_ENABLED=true 要求",
                ):
                    importlib.reload(config_module)
        finally:
            importlib.reload(config_module)


if __name__ == "__main__":
    unittest.main()
