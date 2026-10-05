import os
import tempfile
from pathlib import Path

TEST_ROOT = Path(tempfile.mkdtemp(prefix="doctrad-tests-"))
os.environ.update(DATABASE_URL=os.environ.get("TEST_DATABASE_URL", "sqlite:///"+str(TEST_ROOT / "test.sqlite")), DATA_ROOT=str(TEST_ROOT / "data"), MODEL_ROOT=str(TEST_ROOT / "models"), SESSION_SECRET="a"*64, RUNTIME_SECRET="b"*64, COOKIE_SECURE="false")
import pytest
from sqlalchemy.engine import make_url
if os.environ.get("TEST_DATABASE_URL"):
    url=make_url(os.environ["TEST_DATABASE_URL"])
    if not (url.database or "").endswith("_test"):
        raise RuntimeError("Test database must end with _test; tests reset all application tables")

@pytest.fixture(autouse=True)
def database():
    from app.db import Base,engine
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.web import app
    with TestClient(app, raise_server_exceptions=False) as c: yield c

@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    import socket
    original=socket.socket.connect
    def connect(sock,address):
        if isinstance(address,tuple) and address[0] not in {'127.0.0.1','::1','localhost'}:
            raise AssertionError('External network access forbidden during tests')
        return original(sock,address)
    monkeypatch.setattr(socket.socket,'connect',connect)
