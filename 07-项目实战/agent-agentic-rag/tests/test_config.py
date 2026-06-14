from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import AgenticRAGConfig


class ConfigEnvTest(unittest.TestCase):
    def test_model_paths_can_be_overridden_by_env(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        data_dir = project_root / "data"

        with patch.dict(
            os.environ,
            {
                "EMBEDDING_MODEL_NAME": "/tmp/embed-model",
                "RERANKER_MODEL_NAME": "/tmp/reranker-model",
            },
            clear=False,
        ):
            config = AgenticRAGConfig(project_root=project_root, data_dir=data_dir)

        self.assertEqual(config.embedding_model_name, "/tmp/embed-model")
        self.assertEqual(config.reranker_model_name, "/tmp/reranker-model")


if __name__ == "__main__":
    unittest.main()
