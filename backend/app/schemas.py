from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

FieldType = Literal["text", "date", "select", "phone", "email", "pin", "number", "sensitive"]
Lang = Literal["en", "hi"]


class Option(BaseModel):
    v: str
    en: str
    hi: Optional[str] = None


class FormField(BaseModel):
    id: str
    type: FieldType = "text"
    required: bool = True
    label: dict[str, str]
    hint: Optional[dict[str, str]] = None
    options: Optional[list[Option]] = None
    flag: bool = False
    lang: Optional[Lang] = None
    # Where the field lives on the original page (Google entry id, or the input's name/id).
    # Not used by the app yet; a browser extension needs it to fill the real form later.
    source_key: Optional[str] = None


class FormDef(BaseModel):
    id: str
    title: dict[str, str]
    fields: list[FormField]


# ---- validation ----
class ValidateRequest(BaseModel):
    field: FormField
    raw: str = Field(default="", max_length=2000)


class ValidateResponse(BaseModel):
    valid: bool
    value: Optional[str] = None
    err: Optional[str] = None  # i18n key, e.g. "errPhone"


# ---- parsing ----
class ParseTextRequest(BaseModel):
    text: str = Field(max_length=50_000)


class ParseUrlRequest(BaseModel):
    url: str = Field(max_length=2048)


class ParseResponse(BaseModel):
    title: dict[str, str]
    fields: list[FormField]
    flagged: int  # how many fields the parser could not understand
    source: Optional[str] = None  # "google_forms" or "html" for link reads
    source_url: Optional[str] = None  # the form's final address after redirects (link reads)


# ---- sessions ----
class SessionIn(BaseModel):
    form: FormDef
    answers: dict[str, Any] = {}
    idx: int = Field(default=0, ge=0)
    lang: Lang = "en"


class SessionOut(SessionIn):
    id: str
    expires_at: datetime


class SessionCreated(BaseModel):
    id: str
    expires_at: datetime

# ---- user accounts and basic profile ----
from pydantic import field_validator


class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    mobile_number: Optional[str] = Field(default=None, max_length=20)
    date_of_birth: Optional[str] = Field(default=None, max_length=10)
    address: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    pin_code: Optional[str] = Field(default=None, max_length=10)
    preferred_language: Lang = "en"

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Full name is required")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        import re
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("mobile_number")
    @classmethod
    def clean_mobile(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip()
        import re
        if not re.fullmatch(r"\+?[0-9 ()-]{7,20}", value):
            raise ValueError("Enter a valid mobile number")
        return value

    @field_validator("pin_code")
    @classmethod
    def clean_pin(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not value.isdigit() or not 4 <= len(value) <= 10:
            raise ValueError("Enter a valid PIN code")
        return value


class UserLogin(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    mobile_number: Optional[str] = Field(default=None, max_length=20)
    date_of_birth: Optional[str] = Field(default=None, max_length=10)
    address: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    pin_code: Optional[str] = Field(default=None, max_length=10)
    preferred_language: Optional[Lang] = None


class UserProfile(BaseModel):
    id: str
    full_name: str
    email: str
    mobile_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pin_code: Optional[str] = None
    preferred_language: Lang
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
