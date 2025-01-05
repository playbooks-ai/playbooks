import json
import os
import secrets
from base64 import b64encode

from cryptography.fernet import Fernet, InvalidToken
from database import Base, SessionLocal, engine
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from models import UserSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Generate a secret key for cookie encryption
SECRET_KEY = os.getenv("SECRET_KEY", b64encode(secrets.token_bytes(32)).decode())
fernet = Fernet(b64encode(SECRET_KEY.encode()[:32]))

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        db = SessionLocal()
        response = None
        try:
            session = await self.get_or_create_session(request, db)
            request.state.session = session
            request.state.db = db

            response = await call_next(request)

            # For streaming responses, we need to close the db session after the response is complete
            if not isinstance(response, StreamingResponse):
                # Update session cookie
                session_data = json.dumps({"session_id": session.session_id})
                encrypted_data = fernet.encrypt(session_data.encode())
                response.set_cookie(
                    key="session",
                    value=encrypted_data.decode(),
                    httponly=True,
                    secure=ENVIRONMENT == "production",
                    samesite="lax",
                    max_age=86400,  # 24 hours
                    path="/",
                )

                # Update last active time
                session.update_activity()
                db.commit()
                db.close()

            return response
        except Exception as e:
            db.rollback()
            if response is None or not isinstance(response, StreamingResponse):
                db.close()
            raise e
        finally:
            if response is not None and isinstance(response, StreamingResponse):
                db.close()

    async def get_or_create_session(self, request: Request, db) -> UserSession:
        session_id = None
        session_cookie = request.cookies.get("session")
        print(f"[DEBUG] Session cookie found: {bool(session_cookie)}")

        if session_cookie:
            try:
                encrypted_data = session_cookie.encode()
                decrypted_data = fernet.decrypt(encrypted_data)
                session_id = json.loads(decrypted_data)["session_id"]
                print(f"[DEBUG] Decrypted session_id: {session_id}")
                try:
                    # Ensure tables exist
                    Base.metadata.create_all(bind=engine)
                    # Expire all existing session objects
                    db.expire_all()
                    session = (
                        db.query(UserSession)
                        .filter(UserSession.session_id == session_id)
                        .first()
                    )
                    if session:
                        # Force a reload of the session
                        db.refresh(session)
                    print(f"[DEBUG] Found session in DB: {bool(session)}")
                    if session and session.is_valid():
                        print(
                            f"[DEBUG] Session is valid, runtime_data exists: {bool(session.runtime_data)}"
                        )
                        return session
                    else:
                        print("[DEBUG] Session invalid or expired")
                except Exception as e:
                    print(f"[DEBUG] Database error: {e}")
                    # Fall through to create new session
            except (json.JSONDecodeError, ValueError, InvalidToken) as e:
                print(f"[DEBUG] Session decoding error: {e}")
                pass

        # Create new session
        try:
            print("[DEBUG] Creating new session")
            # Ensure tables exist
            Base.metadata.create_all(bind=engine)
            session = UserSession.create_new()
            db.add(session)
            db.commit()  # Commit immediately after adding
            print(f"[DEBUG] Created new session with id: {session.session_id}")
            return session
        except Exception as e:
            print(f"Error creating session: {e}")
            db.rollback()
            raise
