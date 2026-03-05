# Pydantic Patterns for FastAPI

## Leverage Built-in Validators

Pydantic provides rich validation out of the box — use it before writing custom validators:

```python
from enum import StrEnum
from pydantic import AnyUrl, BaseModel, EmailStr, Field


class MusicBand(StrEnum):
    AEROSMITH = "AEROSMITH"
    QUEEN = "QUEEN"
    ACDC = "AC/DC"


class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128, pattern="^[A-Za-z0-9-_]+$")
    email: EmailStr
    age: int = Field(ge=18, default=None)
    favorite_band: MusicBand | None = None
    website: AnyUrl | None = None
```

## Custom Base Model

Create a project-wide base model for consistent serialization:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict


def datetime_to_gmt_str(dt: datetime) -> str:
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


class CustomModel(BaseModel):
    model_config = ConfigDict(
        json_encoders={datetime: datetime_to_gmt_str},
        populate_by_name=True,
    )

    def serializable_dict(self, **kwargs):
        """Return a dict with only serializable fields."""
        default_dict = self.model_dump()
        return jsonable_encoder(default_dict)
```

Benefits:
- Consistent datetime formatting across all responses
- Single place to add shared serialization logic
- All domain schemas inherit shared behavior

## Split BaseSettings by Domain

A single global `BaseSettings` class gets unwieldy fast. Split config by domain:

```python
# src/auth/config.py
from datetime import timedelta
from pydantic_settings import BaseSettings

class AuthConfig(BaseSettings):
    JWT_ALG: str
    JWT_SECRET: str
    JWT_EXP: int = 5  # minutes
    REFRESH_TOKEN_KEY: str
    REFRESH_TOKEN_EXP: timedelta = timedelta(days=30)
    SECURE_COOKIES: bool = True

auth_settings = AuthConfig()


# src/config.py
from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings
from src.constants import Environment

class Config(BaseSettings):
    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn
    SITE_DOMAIN: str = "myapp.com"
    ENVIRONMENT: Environment = Environment.PRODUCTION
    SENTRY_DSN: str | None = None
    CORS_ORIGINS: list[str]
    CORS_ORIGINS_REGEX: str | None = None
    CORS_HEADERS: list[str]
    APP_VERSION: str = "1.0"

settings = Config()
```

## Response Serialization Gotcha

FastAPI creates your Pydantic response model **twice** — once when you return it, and once internally for validation:

```python
class ProfileResponse(BaseModel):
    @model_validator(mode="after")
    def debug_usage(self):
        print("created pydantic model")  # Prints TWICE per request
        return self

@app.get("/", response_model=ProfileResponse)
async def root():
    return ProfileResponse()
```

The flow: your object → `jsonable_encoder` → dict → validate against `response_model` → JSON.

Be aware of this when using expensive validators or side effects in response models.

## ValueError Becomes ValidationError

If you raise a `ValueError` inside a Pydantic validator used in a request body, FastAPI returns it as a **detailed validation error response** to the client. This can leak internal details.

```python
class ProfileCreate(BaseModel):
    password: str

    @field_validator("password", mode="after")
    @classmethod
    def valid_password(cls, password: str) -> str:
        if not re.match(STRONG_PASSWORD_PATTERN, password):
            raise ValueError(
                "Password must contain at least "
                "one lower character, one upper character, "
                "digit or special symbol"
            )
        return password
```

The `ValueError` message is included verbatim in the 422 response. Keep validation messages user-friendly and avoid leaking implementation details.

## Schema Design Patterns

### Separate input and output schemas

```python
# Input — what the client sends
class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str

# Output — what the API returns
class PostResponse(BaseModel):
    id: UUID4
    title: str
    content: str
    created_at: datetime
    creator: CreatorInfo
```

### Shared base with read-only fields

```python
class PostBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str

class PostCreate(PostBase):
    pass

class PostUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = None

class PostResponse(PostBase):
    id: UUID4
    created_at: datetime
```

### Config for ORM mode

```python
class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    title: str
    created_at: datetime
```
