# FastAPI Dependencies

## Declare Dependencies with `Annotated`

FastAPI has recommended `Annotated[T, Depends(...)]` over the `param: T = Depends(...)`
default-value form since 0.95. The older form works, but it puts a `Depends` object in
the function's default arguments, so the function can no longer be called directly from
tests or other code without passing that sentinel in. `Annotated` leaves defaults alone
and keeps the parameter a normal typed argument.

Store the annotation in a module-level alias and every route reuses one name:

```python
from typing import Annotated, Any

from fastapi import Depends

ValidPost = Annotated[dict[str, Any], Depends(valid_post_id)]
```

Every example below uses that pattern.

## Dependencies as Validation

FastAPI dependencies are not just for DI — they are the primary mechanism for request validation that requires database or external service calls.

```python
# dependencies.py
from typing import Annotated, Any

from fastapi import Depends


async def valid_post_id(post_id: UUID4) -> dict[str, Any]:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()
    return post


ValidPost = Annotated[dict[str, Any], Depends(valid_post_id)]

# router.py — reuse across multiple endpoints
@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post: ValidPost):
    return post

@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(update_data: PostUpdate, post: ValidPost):
    updated = await service.update(id=post["id"], data=update_data)
    return updated

@router.get("/posts/{post_id}/reviews", response_model=list[ReviewResponse])
async def get_post_reviews(post: ValidPost):
    return await reviews_service.get_by_post_id(post["id"])
```

Without the dependency, you'd validate `post_id` existence in every endpoint and duplicate tests.

## Chaining Dependencies

Dependencies can depend on other dependencies, composing validation logic:

```python
from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from src.auth.config import auth_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def parse_jwt_data(token: Annotated[str, Depends(oauth2_scheme)]) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            auth_settings.JWT_SECRET,
            algorithms=[auth_settings.JWT_ALG],
        )
    except JWTError:
        raise InvalidCredentials()
    return {"user_id": payload["id"]}


JwtData = Annotated[dict[str, Any], Depends(parse_jwt_data)]


async def valid_owned_post(post: ValidPost, token_data: JwtData) -> dict[str, Any]:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()
    return post


async def valid_active_creator(token_data: JwtData) -> dict[str, Any]:
    user = await users_service.get_by_id(token_data["user_id"])
    if not user["is_active"]:
        raise UserIsBanned()
    if not user["is_creator"]:
        raise UserNotCreator()
    return user


OwnedPost = Annotated[dict[str, Any], Depends(valid_owned_post)]
ActiveCreator = Annotated[dict[str, Any], Depends(valid_active_creator)]
```

The signing key and algorithm come from `auth_settings`, never from a literal in the
decode call — a hard-coded secret is both a credential in version control and impossible
to rotate per environment. See the `AuthConfig` example in `pydantic-patterns.md`.

## Dependency Caching

Dependencies are **cached per request** by default. If the same dependency appears multiple times in a route's dependency tree, it executes only once.

```python
@router.get("/users/{user_id}/posts/{post_id}", response_model=PostResponse)
async def get_user_post(
    worker: BackgroundTasks,
    post: OwnedPost,      # its chain calls parse_jwt_data
    user: ActiveCreator,  # its chain also calls parse_jwt_data
):
    # parse_jwt_data runs ONCE despite being in both dependency chains
    worker.add_task(notifications_service.send_email, user["id"])
    return post
```

To disable caching for a specific dependency (e.g., if it should run fresh each time):

```python
FreshDep = Annotated[MyResult, Depends(my_dependency, use_cache=False)]


@router.get("/")
async def route(dep: FreshDep):
    ...
```

## Prefer Async Dependencies

Sync dependencies run in a threadpool, just like sync routes. For small non-I/O operations (parsing a header, checking a condition), the threadpool overhead is unnecessary.

```python
# AVOID — runs in threadpool for no reason
def get_current_page(page: Annotated[int, Query(ge=1)] = 1) -> int:
    return page

# PREFER — runs on the event loop, zero overhead
async def get_current_page(page: Annotated[int, Query(ge=1)] = 1) -> int:
    return page
```

`Query`, `Path`, `Header`, and `Body` take the same `Annotated` treatment as `Depends`:
the constraint moves into the annotation and the plain Python default stays a plain
default.

## REST Path Variables for Dependency Reuse

Use consistent path variable names across routes so dependencies can be shared:

```python
# src/profiles/dependencies.py
async def valid_profile_id(profile_id: UUID4) -> Mapping[str, Any]:
    profile = await service.get_by_id(profile_id)
    if not profile:
        raise ProfileNotFound()
    return profile


ValidProfile = Annotated[Mapping[str, Any], Depends(valid_profile_id)]

# src/creators/dependencies.py
async def valid_creator_id(profile: ValidProfile) -> Mapping[str, Any]:
    if not profile["is_creator"]:
        raise ProfileNotCreator()
    return profile


ValidCreator = Annotated[Mapping[str, Any], Depends(valid_creator_id)]

# src/profiles/router.py
@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile: ValidProfile):
    return profile

# src/creators/router.py — uses profile_id (not creator_id) to chain dependencies
@router.get("/creators/{profile_id}", response_model=ProfileResponse)
async def get_creator(creator: ValidCreator):
    return creator
```

## Common Dependency Patterns

### Auth guard as a router dependency

```python
CurrentUser = Annotated[User, Depends(get_current_user)]

# The router-level list stays `Depends(...)` — these run for their side effects
# and nothing binds their return value.
router = APIRouter(dependencies=[Depends(require_authenticated)])


@router.get("/me")
async def get_me(user: CurrentUser):
    return user
```

### Database session dependency

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/items")
async def list_items(db: DbSession):
    result = await db.execute(select(Item))
    return result.scalars().all()
```

### Pagination dependency

```python
async def pagination_params(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, int]:
    return {"skip": skip, "limit": limit}


Pagination = Annotated[dict[str, int], Depends(pagination_params)]


@router.get("/posts")
async def list_posts(pagination: Pagination):
    return await service.list(skip=pagination["skip"], limit=pagination["limit"])
```
