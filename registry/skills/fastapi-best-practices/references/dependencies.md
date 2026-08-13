# FastAPI Dependencies

## Declare Dependencies with `Annotated`

Use `Annotated[T, Depends(...)]` — the style FastAPI has recommended since 0.95 — never `Depends` in the default position:

```python
from typing import Annotated

# AVOID — the "default" is a lie: calling the function directly hands you the Depends sentinel
async def get_post(db: AsyncSession = Depends(get_db)): ...

# PREFER — honest signature: a direct call without the argument raises TypeError
async def get_post(db: Annotated[AsyncSession, Depends(get_db)]): ...
```

Why:

- **Honest defaults** — tests and scripts calling the function directly fail loudly on a missing argument instead of silently receiving the `Depends` object.
- **Real defaults stay available** — `q: Annotated[str | None, Query(max_length=50)] = None`.
- **Reusable aliases** — declare once, reuse in every signature (`DbSession`, `ValidPost` below).
- **Lint-clean** — `Depends()` in a default position trips ruff's B008/FAST002; `Annotated` needs no exemption.

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
from fastapi.security import OAuth2PasswordBearer

async def parse_jwt_data(
    token: Annotated[str, Depends(OAuth2PasswordBearer(tokenUrl="/auth/token"))],
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, "JWT_SECRET", algorithms=["HS256"])
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
```

## Dependency Caching

Dependencies are **cached per request** by default. If the same dependency appears multiple times in a route's dependency tree, it executes only once.

```python
@router.get("/users/{user_id}/posts/{post_id}", response_model=PostResponse)
async def get_user_post(
    worker: BackgroundTasks,
    post: Annotated[Mapping, Depends(valid_owned_post)],     # calls parse_jwt_data
    user: Annotated[Mapping, Depends(valid_active_creator)],  # also calls parse_jwt_data
):
    # parse_jwt_data runs ONCE despite being in both dependency chains
    worker.add_task(notifications_service.send_email, user["id"])
    return post
```

To disable caching for a specific dependency (e.g., if it should run fresh each time):

```python
@router.get("/")
async def route(dep: Annotated[Any, Depends(my_dependency, use_cache=False)]):
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

## REST Path Variables for Dependency Reuse

Use consistent path variable names across routes so dependencies can be shared:

```python
# src/profiles/dependencies.py
async def valid_profile_id(profile_id: UUID4) -> Mapping:
    profile = await service.get_by_id(profile_id)
    if not profile:
        raise ProfileNotFound()
    return profile

ValidProfile = Annotated[Mapping, Depends(valid_profile_id)]

# src/creators/dependencies.py
async def valid_creator_id(profile: ValidProfile) -> Mapping:
    if not profile["is_creator"]:
        raise ProfileNotCreator()
    return profile

ValidCreator = Annotated[Mapping, Depends(valid_creator_id)]

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
router = APIRouter(dependencies=[Depends(require_authenticated)])

@router.get("/me")
async def get_me(user: Annotated[User, Depends(get_current_user)]):
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
