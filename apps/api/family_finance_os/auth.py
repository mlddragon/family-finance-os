from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext
from family_finance_os.models import RecoveryCode, TotpSecret, User, UserSession, utc_now_iso


SESSION_COOKIE_NAME = "ffos_session"
SESSION_IDLE_HOURS = 8
SESSION_ABSOLUTE_DAYS = 7
RECOVERY_CODE_COUNT = 10
_PASSWORD_HASHER = PasswordHasher()
_PENDING_OWNER_ENROLLMENTS: dict[str, dict[str, str]] = {}


class AuthError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class OwnerEnrollmentRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    passphrase: str = Field(min_length=1)
    totp_confirm_code: str = Field(min_length=6, max_length=12)
    recovery_acknowledged: bool = False


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    passphrase: str = Field(min_length=1)
    totp_code: str = Field(min_length=6, max_length=12)


class RecoveryLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    recovery_code: str = Field(min_length=1)


class DevBypassRequest(BaseModel):
    role: str = Field(default="administrator", pattern="^(administrator|contributor|viewer)$")


def normalize_username(username: str) -> str:
    return username.strip().lower()


def auth_status(
    session: Session,
    *,
    session_token: Optional[str],
    client_host: str,
    qa_auth_bypass_available: bool,
) -> dict[str, Any]:
    user_count = session.scalar(select(User).limit(1)) is not None
    resolved = resolve_session(session, session_token=session_token, client_host=client_host)
    return {
        "requires_owner_enrollment": not user_count,
        "authenticated": resolved is not None,
        "user": serialize_user(resolved["user"]) if resolved else None,
        "session": serialize_session(resolved["session"]) if resolved else None,
        "qa_auth_bypass_available": qa_auth_bypass_available,
    }


def enroll_owner(
    session: Session,
    request: OwnerEnrollmentRequest,
    *,
    client_host: str,
) -> dict[str, Any]:
    if session.scalar(select(User).limit(1)) is not None:
        raise AuthError("owner_already_enrolled", "Owner enrollment has already been completed.", 409)

    username = normalize_username(request.username)
    pending = _PENDING_OWNER_ENROLLMENTS.get(username)
    if pending is None:
        pending = {
            "username": username,
            "display_name": request.display_name.strip(),
            "passphrase_hash": hash_passphrase(request.passphrase),
            "totp_secret": pyotp.random_base32(),
        }
        _PENDING_OWNER_ENROLLMENTS[username] = pending

    if not pyotp.TOTP(pending["totp_secret"]).verify(request.totp_confirm_code, valid_window=1):
        return {
            "status": "totp_confirmation_required",
            "totp_secret": pending["totp_secret"],
            "otpauth_uri": pyotp.TOTP(pending["totp_secret"]).provisioning_uri(
                name=username,
                issuer_name="Family Finance OS",
            ),
        }

    if not request.recovery_acknowledged:
        raise AuthError("recovery_acknowledgement_required", "Recovery codes must be acknowledged.", 422)

    user = User(
        username=username,
        display_name=pending["display_name"],
        role="administrator",
        status="active",
        passphrase_hash=pending["passphrase_hash"],
        passphrase_updated_at=utc_now_iso(),
        totp_required=True,
        recovery_required=False,
    )
    session.add(user)
    session.flush()
    session.add(
        TotpSecret(
            user_id=user.id,
            secret_ciphertext=protect_totp_secret(pending["totp_secret"]),
            secret_version=1,
            confirmed_at=utc_now_iso(),
        )
    )
    recovery_codes = create_recovery_codes(session, user.id)
    token, user_session = create_session(session, user, created_from="login", client_host=client_host)
    user.last_login_at = utc_now_iso()
    session.commit()
    _PENDING_OWNER_ENROLLMENTS.pop(username, None)
    return {
        "user": serialize_user(user),
        "session": serialize_session(user_session),
        "totp_secret": pending["totp_secret"],
        "recovery_codes": recovery_codes,
        "session_token": token,
    }


def login(session: Session, request: LoginRequest, *, client_host: str) -> dict[str, Any]:
    user = _active_user_by_username(session, request.username)
    if user is None or not verify_passphrase(user.passphrase_hash, request.passphrase):
        raise AuthError("invalid_credentials", "Invalid username, passphrase, or TOTP code.", 401)
    secret = active_totp_secret(session, user.id)
    if user.totp_required and (
        secret is None or not pyotp.TOTP(secret).verify(request.totp_code, valid_window=1)
    ):
        raise AuthError("invalid_credentials", "Invalid username, passphrase, or TOTP code.", 401)

    token, user_session = create_session(session, user, created_from="login", client_host=client_host)
    user.last_login_at = utc_now_iso()
    session.commit()
    return {"user": serialize_user(user), "session": serialize_session(user_session), "session_token": token}


def recovery_login(
    session: Session,
    request: RecoveryLoginRequest,
    *,
    client_host: str,
) -> dict[str, Any]:
    user = _active_user_by_username(session, request.username)
    if user is None:
        raise AuthError("invalid_recovery_code", "Invalid or already used recovery code.", 401)
    code_hash = hash_secret(request.recovery_code)
    recovery_code = session.scalar(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == code_hash,
            RecoveryCode.status == "active",
        )
    )
    if recovery_code is None:
        raise AuthError("invalid_recovery_code", "Invalid or already used recovery code.", 401)

    token, user_session = create_session(session, user, created_from="recovery", client_host=client_host)
    recovery_code.status = "used"
    recovery_code.used_at = utc_now_iso()
    recovery_code.used_session_id = user_session.id
    user.last_login_at = utc_now_iso()
    session.commit()
    return {"user": serialize_user(user), "session": serialize_session(user_session), "session_token": token}


def logout(session: Session, *, session_token: Optional[str]) -> None:
    if not session_token:
        return
    user_session = session.scalar(
        select(UserSession).where(UserSession.session_token_hash == hash_secret(session_token))
    )
    if user_session is None or user_session.revoked_at is not None:
        return
    user_session.revoked_at = utc_now_iso()
    user_session.revoked_reason = "logout"
    session.commit()


def create_dev_bypass_session(
    session: Session,
    request: DevBypassRequest,
    *,
    client_host: str,
    allowed: bool,
) -> dict[str, Any]:
    if not allowed:
        raise AuthError("dev_bypass_not_allowed", "DEV_MODE auth bypass is not allowed for this runtime.", 403)
    username_by_role = {
        "administrator": "synthetic_admin",
        "contributor": "synthetic_contributor",
        "viewer": "synthetic_viewer",
    }
    display_by_role = {
        "administrator": "SYNTHETIC Administrator",
        "contributor": "SYNTHETIC Contributor",
        "viewer": "SYNTHETIC Viewer",
    }
    username = username_by_role[request.role]
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            display_name=display_by_role[request.role],
            role=request.role,
            status="active",
            passphrase_hash=hash_passphrase(secrets.token_urlsafe(32)),
            passphrase_updated_at=utc_now_iso(),
            totp_required=False,
            recovery_required=False,
        )
        session.add(user)
        session.flush()
    token, user_session = create_session(session, user, created_from="dev_bypass", client_host=client_host)
    user.last_login_at = utc_now_iso()
    session.commit()
    return {"user": serialize_user(user), "session": serialize_session(user_session), "session_token": token}


def resolve_session(
    session: Session,
    *,
    session_token: Optional[str],
    client_host: str,
) -> Optional[dict[str, Any]]:
    if not session_token:
        return None
    now = datetime.now(timezone.utc)
    user_session = session.scalar(
        select(UserSession).where(
            UserSession.session_token_hash == hash_secret(session_token),
            UserSession.revoked_at.is_(None),
        )
    )
    if user_session is None:
        return None
    user = session.get(User, user_session.user_id)
    if user is None or user.status != "active" or user_session.client_host not in {client_host, None}:
        return None
    idle_expires = datetime.fromisoformat(user_session.idle_expires_at)
    absolute_expires = datetime.fromisoformat(user_session.absolute_expires_at)
    if idle_expires <= now or absolute_expires <= now:
        user_session.revoked_at = utc_now_iso()
        user_session.revoked_reason = "expired"
        session.commit()
        return None
    user_session.last_seen_at = now.isoformat()
    user_session.idle_expires_at = min(
        now + timedelta(hours=SESSION_IDLE_HOURS),
        absolute_expires,
    ).isoformat()
    session.commit()
    return {"user": user, "session": user_session, "actor_context": actor_context_for_user(user, user_session)}


def any_users_exist(session: Session) -> bool:
    return session.scalar(select(User.id).limit(1)) is not None


def actor_context_for_user(user: User, user_session: UserSession) -> ActorContext:
    group_keys_by_role = {
        "administrator": ["administrator", "finance_manager", "finance_contributor", "report_viewer"],
        "contributor": ["finance_contributor"],
        "viewer": ["report_viewer"],
    }
    persona_by_role = {
        "administrator": "administrator",
        "contributor": "finance_contributor",
        "viewer": "report_viewer",
    }
    persona_label_by_role = {
        "administrator": "Administrator",
        "contributor": "Finance Contributor",
        "viewer": "Report Viewer",
    }
    source = "dev_bypass" if user_session.created_from == "dev_bypass" else user_session.created_from
    if source == "login":
        source = "auth_session"
    return ActorContext(
        actor_key=f"user:{user.id}",
        actor_type="human",
        display_name=user.display_name,
        persona_key=persona_by_role[user.role],
        persona_label=persona_label_by_role[user.role],
        group_keys=group_keys_by_role[user.role],
        source=source,
    )


def create_session(
    session: Session,
    user: User,
    *,
    created_from: str,
    client_host: str,
) -> tuple[str, UserSession]:
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(48)
    user_session = UserSession(
        user_id=user.id,
        session_token_hash=hash_secret(token),
        created_from=created_from,
        last_seen_at=now.isoformat(),
        idle_expires_at=(now + timedelta(hours=SESSION_IDLE_HOURS)).isoformat(),
        absolute_expires_at=(now + timedelta(days=SESSION_ABSOLUTE_DAYS)).isoformat(),
        client_host=client_host,
    )
    session.add(user_session)
    session.flush()
    return token, user_session


def create_recovery_codes(session: Session, user_id: str) -> list[str]:
    codes = [f"ffos-{secrets.token_urlsafe(9)}" for _ in range(RECOVERY_CODE_COUNT)]
    for index, code in enumerate(codes, start=1):
        session.add(
            RecoveryCode(
                user_id=user_id,
                code_hash=hash_secret(code),
                code_label=f"code-{index:02d}",
                status="active",
            )
        )
    return codes


def active_totp_secret(session: Session, user_id: str) -> Optional[str]:
    record = session.scalar(
        select(TotpSecret).where(
            TotpSecret.user_id == user_id,
            TotpSecret.confirmed_at.is_not(None),
            TotpSecret.disabled_at.is_(None),
        )
    )
    if record is None:
        return None
    return unprotect_totp_secret(record.secret_ciphertext)


def _active_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.scalar(
        select(User).where(
            User.username == normalize_username(username),
            User.status == "active",
        )
    )


def hash_passphrase(passphrase: str) -> str:
    return _PASSWORD_HASHER.hash(passphrase)


def verify_passphrase(passphrase_hash: str, passphrase: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(passphrase_hash, passphrase)
    except VerifyMismatchError:
        return False


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def protect_totp_secret(secret: str) -> str:
    mask = hashlib.sha256(b"family-finance-os-local-totp").digest()
    secret_bytes = secret.encode("utf-8")
    protected = bytes(byte ^ mask[index % len(mask)] for index, byte in enumerate(secret_bytes))
    return "local-v1:" + base64.urlsafe_b64encode(protected).decode("ascii")


def unprotect_totp_secret(secret_ciphertext: str) -> str:
    if not secret_ciphertext.startswith("local-v1:"):
        raise AuthError("invalid_totp_secret", "Stored TOTP secret is not readable.", 500)
    protected = base64.urlsafe_b64decode(secret_ciphertext.removeprefix("local-v1:").encode("ascii"))
    mask = hashlib.sha256(b"family-finance-os-local-totp").digest()
    secret_bytes = bytes(byte ^ mask[index % len(mask)] for index, byte in enumerate(protected))
    return secret_bytes.decode("utf-8")


def secure_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
        "totp_required": user.totp_required,
        "recovery_required": user.recovery_required,
    }


def serialize_session(user_session: UserSession) -> dict[str, Any]:
    return {
        "id": user_session.id,
        "created_from": user_session.created_from,
        "last_seen_at": user_session.last_seen_at,
        "idle_expires_at": user_session.idle_expires_at,
        "absolute_expires_at": user_session.absolute_expires_at,
    }
