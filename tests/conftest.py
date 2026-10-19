import atexit
import os
import shutil
import tempfile
from pathlib import Path

TEST_DIR = Path(tempfile.mkdtemp(prefix="exam-agent-test-"))
os.environ["DATA_DIR"] = str(TEST_DIR)
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_DIR / 'test.db').as_posix()}"
os.environ["DEEPSEEK_API_KEY"] = ""

atexit.register(shutil.rmtree, TEST_DIR, ignore_errors=True)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
