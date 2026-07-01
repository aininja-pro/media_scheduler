"""
User Management Router (Admin console)

Lets admins add, list, and remove people who can sign in to the scheduler.
Users are stored in Supabase Auth (auth.users) - Supabase handles password
hashing. The admin flag lives in each user's user_metadata as `is_admin`.

Access control: every endpoint here requires a Supabase access token (Bearer)
belonging to a user whose user_metadata.is_admin is true. The legacy shared
"driveshop" login has no Supabase token, so it can never reach these routes.

Author: Ray Rierson
Date: 2026-06-30
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional
from pydantic import BaseModel, EmailStr
import logging

from ..services.database import db_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/users", tags=["User Management"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = ""
    is_admin: bool = False


class ResetPasswordRequest(BaseModel):
    password: str


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def require_admin(authorization: Optional[str] = Header(None)) -> dict:
    """Verify the caller is a signed-in admin, else raise 401/403.

    Expects `Authorization: Bearer <supabase_access_token>`. The token is
    verified against Supabase; the user's user_metadata.is_admin must be true.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()

    try:
        result = db_service.client.auth.get_user(token)
    except Exception as e:
        logger.warning(f"Admin token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = getattr(result, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    metadata = user.user_metadata or {}
    if not metadata.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    return {"id": user.id, "email": user.email}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_user(user) -> dict:
    """Flatten a Supabase Auth user into the shape the frontend needs."""
    metadata = user.user_metadata or {}
    return {
        "id": user.id,
        "email": user.email,
        "full_name": metadata.get("full_name", ""),
        "is_admin": bool(metadata.get("is_admin", False)),
        "created_at": str(user.created_at) if user.created_at else None,
        "last_sign_in_at": str(user.last_sign_in_at) if user.last_sign_in_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_users(admin: dict = Depends(require_admin)):
    """List all users (admins only)."""
    try:
        users = db_service.client.auth.admin.list_users()
        # Newer clients may wrap the list; normalize to a plain list.
        if hasattr(users, "users"):
            users = users.users
        return [_serialize_user(u) for u in users]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list users: {e}")


@router.post("")
async def create_user(body: CreateUserRequest, admin: dict = Depends(require_admin)):
    """Create a new user with a temporary password (admins only)."""
    try:
        result = db_service.client.auth.admin.create_user({
            "email": body.email,
            "password": body.password,
            "email_confirm": True,  # no confirmation email; usable immediately
            "user_metadata": {
                "full_name": body.full_name or "",
                "is_admin": body.is_admin,
            },
        })
        logger.info(f"Admin {admin['email']} created user {body.email}")
        return _serialize_user(result.user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create user {body.email}: {e}")
        # Supabase returns a clear message for duplicate emails / weak passwords.
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    """Delete a user (admins only)."""
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    try:
        db_service.client.auth.admin.delete_user(user_id)
        logger.info(f"Admin {admin['email']} deleted user {user_id}")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}/reset-password")
async def reset_password(user_id: str, body: ResetPasswordRequest,
                         admin: dict = Depends(require_admin)):
    """Set a new password for a user (admins only)."""
    try:
        db_service.client.auth.admin.update_user_by_id(user_id, {"password": body.password})
        logger.info(f"Admin {admin['email']} reset password for user {user_id}")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset password for {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
