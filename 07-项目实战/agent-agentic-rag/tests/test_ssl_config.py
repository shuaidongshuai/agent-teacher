from __future__ import annotations

import unittest

from app.llm_client import _parse_bool_env


class SSLConfigTest(unittest.TestCase):
    def test_ssl_verify_defaults_to_false(self) -> None:
        self.assertFalse(_parse_bool_env(None, default=False))

    def test_ssl_verify_parses_true_values(self) -> None:
        self.assertTrue(_parse_bool_env("true", default=False))
        self.assertTrue(_parse_bool_env("1", default=False))
        self.assertTrue(_parse_bool_env("yes", default=False))


if __name__ == "__main__":
    unittest.main()
