"""Authentication routes - Email, VK, Yandex OAuth"""
from fastapi import APIRouter, HTTPException, Request
from typing import Optional
from datetime import datetime, timezone
import os
import httpx
import bcrypt
import secrets

from models.user import (
    User, UserCreate, UserLogin, TokenResponse,
    UserRole, AuthProvider, UserProfile, OAuthData
)
from utils.database import get_db
from utils.rate_limit import limiter
from utils.auth import (  # noqa: F401 — get_current_user реэкспортируется для старых импортов
    create_token, verify_token, verify_token_with_grace, get_current_user, extract_bearer_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# OAuth settings
VK_CLIENT_ID = os.environ.get("VK_CLIENT_ID", "")
VK_CLIENT_SECRET = os.environ.get("VK_CLIENT_SECRET", "")
VK_REDIRECT_URI = os.environ.get("VK_REDIRECT_URI", "")

YANDEX_CLIENT_ID = os.environ.get("YANDEX_CLIENT_ID", "")
YANDEX_CLIENT_SECRET = os.environ.get("YANDEX_CLIENT_SECRET", "")
YANDEX_REDIRECT_URI = os.environ.get("YANDEX_REDIRECT_URI", "")


def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode(), hashed.encode())


# === EMAIL REGISTRATION ===

MIN_PASSWORD_LENGTH = 8


@router.post("/register", response_model=TokenResponse)
@limiter.limit("10/hour")
async def register(request: Request, data: UserCreate):
    """Register new user with email"""
    if len(data.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")

    db = await get_db()

    # Check if email exists
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Электронная почта уже зарегистрирована")
    
    # Check if username exists
    existing = await db.users.find_one({"username": data.username})
    if existing:
        raise HTTPException(status_code=400, detail="Имя пользователя занято")
    
    # Create user
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        profile=data.profile or UserProfile(),
        auth_provider=AuthProvider.EMAIL
    )
    
    doc = user.model_dump(by_alias=True)
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    
    await db.users.insert_one(doc)
    
    # Create token
    token, expires_in = create_token(doc["_id"], user.role.value)
    
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user={
            "id": doc["_id"],
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "profile": user.profile.model_dump()
        }
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(request: Request, data: UserLogin):
    """Login with email and password"""
    db = await get_db()
    
    user = await db.users.find_one({"email": data.email})
    
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    if not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Используйте вход через соцсеть")
    
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    if user.get("banned"):
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")
    
    # Update last login
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Create token
    token, expires_in = create_token(user["_id"], user.get("role", "user"))
    
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user={
            "id": user["_id"],
            "username": user["username"],
            "email": user.get("email"),
            "role": user.get("role", "user"),
            "profile": user.get("profile", {})
        }
    )


@router.get("/me")
async def get_me(request: Request):
    """Get current user info"""
    user = await get_current_user(request)
    
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    return {
        "id": user["_id"],
        "username": user["username"],
        "email": user.get("email"),
        "role": user.get("role", "user"),
        "profile": user.get("profile", {}),
        "stats": user.get("stats", {})
    }


@router.post("/refresh")
async def refresh_token(request: Request):
    """Refresh JWT token. Accepts valid or recently expired tokens (within 30-day grace period)."""
    old_token = extract_bearer_token(request)
    if not old_token:
        raise HTTPException(status_code=401, detail="Токен не предоставлен")

    payload = verify_token_with_grace(old_token)

    if not payload:
        raise HTTPException(status_code=401, detail="Токен невалиден или истёк слишком давно")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Невалидный токен")

    db = await get_db()
    user = await db.users.find_one({"_id": user_id})

    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    if user.get("banned"):
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")

    # Issue a fresh token
    token, expires_in = create_token(user["_id"], user.get("role", "user"))

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user={
            "id": user["_id"],
            "username": user["username"],
            "email": user.get("email"),
            "role": user.get("role", "user"),
            "profile": user.get("profile", {})
        }
    )


# === VK OAUTH ===

@router.get("/vk")
async def vk_login():
    """Redirect to VK OAuth"""
    if not VK_CLIENT_ID:
        raise HTTPException(status_code=501, detail="VK OAuth не настроен")
    
    state = secrets.token_urlsafe(16)
    auth_url = (
        f"https://oauth.vk.com/authorize?"
        f"client_id={VK_CLIENT_ID}&"
        f"redirect_uri={VK_REDIRECT_URI}&"
        f"display=page&"
        f"scope=email&"
        f"response_type=code&"
        f"state={state}&"
        f"v=5.131"
    )
    return {"url": auth_url, "state": state}


@router.get("/vk/callback")
async def vk_callback(code: str, state: Optional[str] = None):
    """VK OAuth callback"""
    if not VK_CLIENT_ID or not VK_CLIENT_SECRET:
        raise HTTPException(status_code=501, detail="VK OAuth не настроен")
    
    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_response = await client.get(
            "https://oauth.vk.com/access_token",
            params={
                "client_id": VK_CLIENT_ID,
                "client_secret": VK_CLIENT_SECRET,
                "redirect_uri": VK_REDIRECT_URI,
                "code": code
            }
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Ошибка авторизации VK")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        vk_user_id = str(token_data.get("user_id"))
        email = token_data.get("email")
        
        # Get user info from VK
        user_response = await client.get(
            "https://api.vk.com/method/users.get",
            params={
                "user_ids": vk_user_id,
                "fields": "photo_200,screen_name",
                "access_token": access_token,
                "v": "5.131"
            }
        )
        
        vk_user = user_response.json().get("response", [{}])[0]
    
    db = await get_db()
    
    # Find or create user
    user = await db.users.find_one({"oauth.vk_id": vk_user_id})
    
    if not user:
        # Check if email already exists
        if email:
            user = await db.users.find_one({"email": email})
            if user:
                # Link VK to existing account
                await db.users.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "oauth.vk_id": vk_user_id,
                        "oauth.vk_data": vk_user
                    }}
                )
        
        if not user:
            # Create new user
            username = vk_user.get("screen_name") or f"vk_{vk_user_id}"
            
            # Ensure unique username
            base_username = username
            counter = 1
            while await db.users.find_one({"username": username}):
                username = f"{base_username}_{counter}"
                counter += 1
            
            new_user = User(
                username=username,
                email=email,
                auth_provider=AuthProvider.VK,
                profile=UserProfile(
                    full_name=f"{vk_user.get('first_name', '')} {vk_user.get('last_name', '')}".strip(),
                    avatar=vk_user.get("photo_200")
                ),
                oauth=OAuthData(
                    vk_id=vk_user_id,
                    vk_data=vk_user
                ),
                verified=True
            )
            
            doc = new_user.model_dump(by_alias=True)
            doc["created_at"] = doc["created_at"].isoformat()
            doc["updated_at"] = doc["updated_at"].isoformat()
            
            await db.users.insert_one(doc)
            user = doc
    
    # Update last login
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Create token
    token, expires_in = create_token(user["_id"], user.get("role", "user"))
    
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user={
            "id": user["_id"],
            "username": user["username"],
            "email": user.get("email"),
            "role": user.get("role", "user"),
            "profile": user.get("profile", {})
        }
    )


# === YANDEX OAUTH ===

@router.get("/yandex")
async def yandex_login():
    """Redirect to Yandex OAuth"""
    if not YANDEX_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Yandex OAuth не настроен")
    
    state = secrets.token_urlsafe(16)
    auth_url = (
        f"https://oauth.yandex.ru/authorize?"
        f"response_type=code&"
        f"client_id={YANDEX_CLIENT_ID}&"
        f"redirect_uri={YANDEX_REDIRECT_URI}&"
        f"state={state}"
    )
    return {"url": auth_url, "state": state}


@router.get("/yandex/callback")
async def yandex_callback(code: str, state: Optional[str] = None):
    """Yandex OAuth callback"""
    if not YANDEX_CLIENT_ID or not YANDEX_CLIENT_SECRET:
        raise HTTPException(status_code=501, detail="Yandex OAuth не настроен")
    
    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth.yandex.ru/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": YANDEX_CLIENT_ID,
                "client_secret": YANDEX_CLIENT_SECRET
            }
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Ошибка авторизации Yandex")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        # Get user info
        user_response = await client.get(
            "https://login.yandex.ru/info",
            headers={"Authorization": f"OAuth {access_token}"}
        )
        
        yandex_user = user_response.json()
        yandex_user_id = str(yandex_user.get("id"))
        email = yandex_user.get("default_email")
    
    db = await get_db()
    
    # Find or create user
    user = await db.users.find_one({"oauth.yandex_id": yandex_user_id})
    
    if not user:
        # Check if email already exists
        if email:
            user = await db.users.find_one({"email": email})
            if user:
                # Link Yandex to existing account
                await db.users.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "oauth.yandex_id": yandex_user_id,
                        "oauth.yandex_data": yandex_user
                    }}
                )
        
        if not user:
            # Create new user
            username = yandex_user.get("login") or f"ya_{yandex_user_id}"
            
            # Ensure unique username
            base_username = username
            counter = 1
            while await db.users.find_one({"username": username}):
                username = f"{base_username}_{counter}"
                counter += 1
            
            avatar_id = yandex_user.get("default_avatar_id")
            avatar_url = f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200" if avatar_id else None
            
            new_user = User(
                username=username,
                email=email,
                auth_provider=AuthProvider.YANDEX,
                profile=UserProfile(
                    full_name=yandex_user.get("real_name") or yandex_user.get("display_name"),
                    avatar=avatar_url
                ),
                oauth=OAuthData(
                    yandex_id=yandex_user_id,
                    yandex_data=yandex_user
                ),
                verified=True
            )
            
            doc = new_user.model_dump(by_alias=True)
            doc["created_at"] = doc["created_at"].isoformat()
            doc["updated_at"] = doc["updated_at"].isoformat()
            
            await db.users.insert_one(doc)
            user = doc
    
    # Update last login
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Create token
    token, expires_in = create_token(user["_id"], user.get("role", "user"))
    
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user={
            "id": user["_id"],
            "username": user["username"],
            "email": user.get("email"),
            "role": user.get("role", "user"),
            "profile": user.get("profile", {})
        }
    )


@router.post("/logout")
async def logout():
    """Logout (client should discard token)"""
    return {"message": "Выход выполнен"}
