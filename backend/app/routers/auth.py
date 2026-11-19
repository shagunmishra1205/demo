from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..auth_security import create_access_token, hash_password, read_access_token, verify_password
from ..database import get_db
from ..models import User
from ..schemas import AuthResponse, UserLogin, UserProfile, UserProfileUpdate, UserRegister

router = APIRouter(prefix="/api/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue")
    user_id = read_access_token(credentials.credentials)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session is invalid or expired. Please sign in again.")
    return user


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(access_token=create_access_token(user.id), user=UserProfile.model_validate(user))


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    values = body.model_dump()
    password = values.pop("password")
    user = User(**values, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # Handles two registration requests racing to claim the same email.
        if db.query(User).filter(User.email == body.email).first():
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
        raise
    db.refresh(user)
    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(body: UserLogin, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return _auth_response(user)


@router.get("/me", response_model=UserProfile)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserProfile)
def update_profile(
    body: UserProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True)
    if "full_name" in changes and changes["full_name"] is not None:
        changes["full_name"] = " ".join(changes["full_name"].split())
    if "mobile_number" in changes and changes["mobile_number"]:
        import re
        if not re.fullmatch(r"\+?[0-9 ()-]{7,20}", changes["mobile_number"].strip()):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a valid mobile number")
        changes["mobile_number"] = changes["mobile_number"].strip()
    if "pin_code" in changes and changes["pin_code"]:
        pin = changes["pin_code"].strip()
        if not pin.isdigit() or not 4 <= len(pin) <= 10:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a valid PIN code")
        changes["pin_code"] = pin
    for key, value in changes.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(user: User = Depends(get_current_user)):
    # Access tokens are stateless; the client must discard its token on logout.
    return {"message": "Signed out. Please discard the access token."}
