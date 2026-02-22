---
name: modern-python-development
description: This skill should be used when the user asks to "write Python code", "create a Python module", "set up a Python project", "review Python code", "refactor Python", "add type hints", "fix Python style", or when generating any Python source code. Provides modern Python 3.12+ best practices covering syntax, type hints, error handling, project structure, and idiomatic patterns. Does not cover any specific library or framework.
version: 0.1.0
---

# Modern Python Development (3.12+)

Pure Python best practices for writing clean, idiomatic, and type-safe code. All guidance targets Python 3.12+ and covers only the standard language and stdlib — no third-party libraries or frameworks.

## Naming Conventions

| Element          | Convention        | Example                       |
|------------------|-------------------|-------------------------------|
| Module           | `snake_case`      | `data_loader.py`              |
| Package          | `lowercase`       | `utils/`, `core/`             |
| Class            | `PascalCase`      | `UserAccount`                 |
| Function/Method  | `snake_case`      | `get_user_by_id()`            |
| Variable         | `snake_case`      | `retry_count`                 |
| Constant         | `UPPER_SNAKE`     | `MAX_RETRIES`                 |
| Type alias       | `PascalCase`      | `type UserId = int`           |
| Private          | `_leading`        | `_internal_cache`             |
| Name-mangled     | `__double`        | `__secret` (rarely needed)    |
| Dunder           | `__name__`        | Reserved for Python protocols |

Prefix boolean variables and functions with `is_`, `has_`, `can_`, or `should_`.

## Modern Syntax Essentials

### Prefer modern constructs over legacy equivalents

| Legacy                              | Modern (3.12+)                    |
|-------------------------------------|-----------------------------------|
| `Union[X, Y]`                       | `X \| Y`                         |
| `Optional[X]`                       | `X \| None`                      |
| `TypeAlias = ...`                   | `type Alias = ...`               |
| `List[str]`, `Dict[str, int]`      | `list[str]`, `dict[str, int]`    |
| `Tuple[int, ...]`                   | `tuple[int, ...]`                |
| `if/elif/elif` chains on a value    | `match`/`case`                   |
| `os.path.join()`                    | `pathlib.Path`                   |
| `"{}".format(x)`                    | `f"{x}"`                         |

### Structural pattern matching

Use `match`/`case` for value dispatch, destructuring, and type narrowing — not as a simple switch replacement. See `references/modern-syntax.md` for detailed patterns.

```python
match command:
    case {"action": "move", "direction": str(d)}:
        handle_move(d)
    case {"action": "quit"}:
        handle_quit()
    case _:
        handle_unknown(command)
```

### The `type` statement (3.12+)

```python
type Vector = list[float]
type Result[T] = T | Error
type Handler[**P] = Callable[P, Awaitable[None]]
```

## Type Hints

Apply type hints to all function signatures, class attributes, and module-level variables. Omit return type only for `__init__`.

```python
def calculate_total(items: list[float], *, tax_rate: float = 0.0) -> float:
    ...
```

Key rules:
- Use built-in generics: `list[str]`, `dict[str, int]`, `tuple[int, ...]`, `set[str]`
- Use `X | None` instead of `Optional[X]`
- Use `type` statement for aliases, not bare assignment
- Prefer `Protocol` over `ABC` when only structural typing is needed
- Use `@override` decorator (3.12+) when overriding base class methods
- Use `Self` for methods returning the instance type

For comprehensive typing patterns including generics, `Protocol`, `TypeGuard`, `TypeVar`, and `ParamSpec`, consult `references/type-hints.md`.

## Error Handling

### Hierarchy

Define domain errors as a hierarchy inheriting from a project-level base:

```python
class AppError(Exception):
    """Base for all application errors."""

class ValidationError(AppError):
    """Invalid input data."""

class NotFoundError(AppError):
    """Requested resource does not exist."""
```

### Rules

- Catch the narrowest exception type possible. Never use bare `except:`.
- Raise from the original cause: `raise NewError(...) from original`.
- Use `ExceptionGroup` and `except*` for concurrent error aggregation.
- Use context managers (`with` statement) for resource cleanup — avoid manual `try/finally`.
- Document raised exceptions in the docstring, not with annotations.

### Exception groups (3.11+)

```python
try:
    async with TaskGroup() as tg:
        tg.create_task(validate_name(data))
        tg.create_task(validate_email(data))
except* ValidationError as eg:
    errors = eg.exceptions
```

## Dataclasses and Data Modeling

Prefer `dataclasses` for data containers. Use `__slots__` for memory-critical paths.

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class Coordinate:
    x: float
    y: float
    label: str = ""
    tags: list[str] = field(default_factory=list)
```

- Use `frozen=True` for value objects and immutable data.
- Use `slots=True` (3.10+) to reduce memory and prevent attribute typos.
- Use `kw_only=True` when the class has more than 3 fields.
- Use `field(default_factory=...)` for mutable defaults.

## Project Structure

Follow the `src` layout for any project intended to be packaged or tested:

```
project-name/
├── pyproject.toml
├── src/
│   └── package_name/
│       ├── __init__.py
│       ├── core/
│       ├── models/
│       └── utils/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
└── scripts/
```

Key conventions:
- Single source of truth for version and metadata in `pyproject.toml`.
- The `src/` layout prevents accidental imports from the working directory.
- Keep `__init__.py` files minimal — define the public API, not implementation.
- Organize by domain, not by technical role (prefer `users/` over `services/`).

For complete project structure guidance including `pyproject.toml` conventions, module organization, and entry points, consult `references/project-structure.md`.

## Idiomatic Patterns

### Prefer stdlib over hand-rolling

- `pathlib.Path` for all file system operations.
- `enum.Enum` / `enum.StrEnum` for fixed sets of values.
- `contextlib.contextmanager` for simple resource management.
- `functools.cache` / `functools.lru_cache` for memoization.
- `itertools` for iterator composition.
- `collections.abc` for abstract container checks.

### Generator expressions over list comprehensions when only iterating

```python
total = sum(item.price for item in cart)  # generator — no intermediate list
```

### Walrus operator for capture-and-test

```python
if (match := pattern.search(line)) is not None:
    process(match.group(1))
```

### `__all__` for public API

```python
__all__ = ["UserService", "create_user", "UserError"]
```

For comprehensive patterns including Protocols, ABCs, descriptors, context managers, enums, and more, consult `references/patterns.md`.

## Additional Resources

### Reference Files

For detailed guidance beyond this overview, consult:
- **`references/modern-syntax.md`** — Structural pattern matching, `type` statement, exception groups, `@override`, f-string details
- **`references/type-hints.md`** — Generics, Protocol, TypeGuard, TypeVar, ParamSpec, Self, Overload
- **`references/patterns.md`** — Idiomatic patterns: Protocols, enums, context managers, generators, pathlib, ABC
- **`references/project-structure.md`** — `pyproject.toml` conventions, src layout, module organization, entry points, `__init__.py` patterns
