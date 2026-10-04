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
    age: int | None = Field(default=None, ge=18)
    favorite_band: MusicBand | None = None
    website: AnyUrl | None = None
```

## Custom Base Model

Create a project-wide base model, plus annotated types for consistent serialization. `json_encoders` is deprecated in Pydantic v2 — custom serialization lives in annotated serializers (`PlainSerializer`) or `@field_serializer`, not in `model_config`:

```python
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, PlainSerializer


def datetime_to_gmt_str(dt: datetime) -> str:
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


# Declare once; every schema field annotated with it serializes consistently
UTCDateTime = Annotated[datetime, PlainSerializer(datetime_to_gmt_str, when_used="json")]


class CustomModel(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
```

```python
class PostResponse(CustomModel):
    id: UUID4
    created_at: UTCDateTime  # serialized via datetime_to_gmt_str
```

Benefits:

- Consistent datetime formatting across all responses via one annotated type
- Single place (`CustomModel`) to add shared config and behavior
- All domain schemas inherit shared behavior

Notes:

- `populate_by_name=True` is superseded in Pydantic 2.11+ by `validate_by_name=True` + `validate_by_alias=True` (the pair is the exact equivalent; `populate_by_name` is slated for deprecation in v3).
- No `serializable_dict` helper is needed: `model_dump(mode="json")` returns a JSON-compatible dict natively — `jsonable_encoder` over `model_dump()` is a v1-era workaround.

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

The unit of the split is the **class**, not the file: each domain gets its own `BaseSettings` class, initialized independently. Where those classes live follows the project's structure conventions — the paths above show a per-domain-module layout; a project that keeps one top-level `config.py` (e.g. the vertical-slice layout of the companion `fastapi-vertical-slice-architecture` skill) holds `AuthConfig` and `Config` as two classes in that single file, and the split survives intact.

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

The flow: your object → validated into a second `response_model` instance → serialized (`model_dump`) → JSON.

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

### Never share a base across request and response

```python
# Preferred — each schema declares its own fields
class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str

class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None

class PostResponse(BaseModel):
    id: UUID4
    title: str
    content: str
    created_at: datetime
```

```python
# Avoid — one base spanning both directions
class PostBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str

class PostCreate(PostBase):
    pass                       # a subclass that adds nothing — a pass-through

class PostUpdate(BaseModel):   # cannot inherit PostBase — its optionality differs
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None

class PostResponse(PostBase):  # now on PostCreate's release schedule
    id: UUID4
    created_at: datetime
```

Two duplicated field declarations are cheaper than the coupling. The first time the response needs a field the request does not carry — or the same field under a different constraint — the shared base fractures, and the path of least resistance is widening it and defaulting fields to `None`. That is how a single god-schema with every field `X | None` arrives, and by then request validation is gone.

The `Avoid` block reports its own failure: `PostUpdate` cannot inherit `PostBase`, because its optionality differs. A base may be shared only **within** one direction, and only when the fields are identical in both type and constraint — rarer than it looks. `PostCreate` and `PostUpdate` fail that test, which is why the preferred form declares all three independently.

### `from_attributes` for ORM objects

Read attributes off SQLAlchemy (or any) objects — the v2 rename of v1's `orm_mode`:

```python
class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    title: str
    created_at: datetime
```

`from_attributes` is how an ORM object becomes a response — it is not permission to skip the response schema. `response_model` is always a Pydantic class, never the SQLAlchemy model:

```python
# Preferred — the Pydantic schema is the contract; from_attributes reads the ORM object
@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: UUID4, db: DbSession) -> Post:
    ...
```

```python
# Avoid — the ORM model as the response contract
@router.get("/posts/{post_id}", response_model=Post)   # Post is the SQLAlchemy model
async def get_post(post_id: UUID4, db: DbSession):
    ...
```

The `Avoid` form satisfies "always set `response_model`" and still ships every column. The failure is silent and deferred: the endpoint is correct today, and starts leaking the day someone adds `password_hash`, `internal_margin`, or a soft-delete flag to the table. The preferred form fails closed — a new column reaches a client only when someone adds the field to `PostResponse` on purpose.
