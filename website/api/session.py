import json
import os
import secrets
from base64 import b64encode

from cryptography.fernet import Fernet
from database import SessionLocal, Base, engine
from fastapi import Request, Response
from models import UserSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

# Generate a secret key for cookie encryption
SECRET_KEY = os.getenv("SECRET_KEY", b64encode(secrets.token_bytes(32)).decode())
fernet = Fernet(b64encode(SECRET_KEY.encode()[:32]))


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        db = SessionLocal()
        try:
            session = await self.get_or_create_session(request, db)
            request.state.session = session
            request.state.db = db

            response = await call_next(request)

            # Update session cookie
            session_data = json.dumps({"session_id": session.session_id})
            encrypted_data = fernet.encrypt(session_data.encode())
            response.set_cookie(
                key="session",
                value=encrypted_data.decode(),
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=86400,  # 24 hours
            )

            # Update last active time
            session.update_activity()
            db.commit()

            return response
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    async def get_or_create_session(self, request: Request, db) -> UserSession:
        session_id = None
        session_cookie = request.cookies.get("session")

        if session_cookie:
            try:
                encrypted_data = session_cookie.encode()
                decrypted_data = fernet.decrypt(encrypted_data)
                session_id = json.loads(decrypted_data)["session_id"]
                try:
                    # Ensure tables exist
                    Base.metadata.create_all(bind=engine)
                    session = (
                        db.query(UserSession)
                        .filter(UserSession.session_id == session_id)
                        .first()
                    )
                    if session and session.is_valid():
                        return session
                except Exception as e:
                    print(f"Database error: {e}")
                    # Fall through to create new session
            except:
                pass

        # Create new session
        try:
            # Ensure tables exist
            Base.metadata.create_all(bind=engine)
            session = UserSession.create_new()
            db.add(session)
            db.commit()  # Commit immediately after adding
            return session
        except Exception as e:
            print(f"Error creating session: {e}")
            db.rollback()
            raise
