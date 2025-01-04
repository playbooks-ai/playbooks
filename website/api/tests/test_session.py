import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from database import Base, SessionLocal
from fastapi import FastAPI
from fastapi.testclient import TestClient
from models import UserSession
from session import SessionMiddleware, fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Use SQLite in-memory database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Store original SessionLocal
OriginalSessionLocal = SessionLocal


def get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_app():
    app = FastAPI()

    @app.get("/api/health")
    def health_check():
        return {"status": "healthy"}

    # Override the SessionLocal in the session middleware
    import session
    session.SessionLocal = TestingSessionLocal

    # Add session middleware
    app.add_middleware(SessionMiddleware)

    return app


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db():
    """Get test database session"""
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    """Test client with clean session for each test"""
    app = create_test_app()
    app.dependency_overrides[OriginalSessionLocal] = get_test_db
    client = TestClient(app)
    # Set cookies at client level instead of per-request
    client.cookies.set("session", "")
    return client


@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables"""
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SECRET_KEY", "test_secret_key_for_session_encryption")


def test_session_creation(client):
    """Test that a new session is created on first request"""
    response = client.get("/api/health")
    assert response.status_code == 200

    # Verify session cookie was set
    assert "session" in response.cookies
    session_cookie = response.cookies["session"]
    assert session_cookie

    # Decrypt session cookie
    encrypted_data = session_cookie.encode()
    decrypted_data = fernet.decrypt(encrypted_data)
    session_data = json.loads(decrypted_data)

    # Verify session data
    assert "session_id" in session_data
    assert uuid.UUID(session_data["session_id"])


def test_session_persistence(client):
    """Test that session data persists across requests"""
    # First request creates session
    response1 = client.get("/api/health")
    session_cookie1 = response1.cookies["session"]
    session_data1 = json.loads(fernet.decrypt(session_cookie1.encode()))

    # Second request should reuse session
    client.cookies.set("session", session_cookie1)
    response2 = client.get("/api/health")
    session_cookie2 = response2.cookies["session"]
    session_data2 = json.loads(fernet.decrypt(session_cookie2.encode()))

    # Session IDs should match even if the cookie changes due to timestamp updates
    assert session_data1["session_id"] == session_data2["session_id"]


def test_invalid_session(client):
    """Test handling of invalid session cookies"""
    # Make request with invalid session cookie
    client.cookies.set("session", "invalid_session_cookie")
    response = client.get("/api/health")
    assert response.status_code == 200

    # Should get a new session cookie
    assert "session" in response.cookies


def test_session_database(client, test_db):
    """Test that sessions are properly stored in database"""
    response = client.get("/api/health")
    
    sessions = test_db.query(UserSession).all()
    assert len(sessions) == 1
    assert sessions[0].is_valid() is True


def test_session_expiry(test_db):
    """Test session expiration"""
    # Create a session that's expired
    expired_time = datetime(2020, 1, 1).replace(tzinfo=None)  # A time in the past
    session = UserSession(
        session_id=str(uuid.uuid4()),
        created_at=expired_time,
        last_active=expired_time,
    )
    test_db.add(session)
    test_db.commit()

    # Verify session is expired
    assert session.is_valid() is False
