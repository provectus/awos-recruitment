# Python Type Hints Reference (3.12+)

## Contents
- Built-in Generics
- Union Types
- Type Aliases with `type` Statement
- TypeVar and Generics (generic functions, bounded generics, generic classes)
- Protocol (structural typing, runtime-checkable, generic protocols)
- Self Type
- TypeGuard and TypeIs
- Overload
- ParamSpec
- Callable Types
- Common Patterns (TypedDict, Literal, Never)
- Rules Summary

## Built-in Generics

As of Python 3.9+, use the built-in containers directly and never import their
capitalised `typing` aliases (`List`, `Dict`, `Tuple`, `Set`, `FrozenSet`), which are
deprecated:

```python
# Correct
names: list[str] = []
config: dict[str, int] = {}
coords: tuple[float, float] = (0.0, 0.0)
unique: set[str] = set()
frozen: frozenset[int] = frozenset()

# Wrong — deprecated aliases
from typing import List, Dict, Tuple, Set  # Do not use
```

This rule is about the deprecated container aliases only. The `typing` module remains
the right import for everything that has no builtin equivalent — `Protocol`, `Self`,
`Literal`, `TypedDict`, `overload`, `override`, `Never` and friends — and the abstract
containers (`Iterable`, `Sequence`, `Callable`, `Iterator`) come from
`collections.abc`.

## Union Types

Use the `|` operator (3.10+):

```python
def parse(value: str | int) -> float:
    ...

def find_user(user_id: int) -> User | None:
    ...
```

Never use `Union[X, Y]` or `Optional[X]`.

## Type Aliases with `type` Statement

```python
type UserId = int
type JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
type Result[T] = T | Error
type Predicate[T] = Callable[[T], bool]
```

## TypeVar and Generics

### Generic functions

```python
def first[T](items: Sequence[T]) -> T:
    return items[0]
```

The `[T]` syntax (3.12+) replaces explicit `TypeVar` declarations:

```python
# Legacy — avoid
T = TypeVar("T")
def first(items: Sequence[T]) -> T: ...

# Modern — prefer
def first[T](items: Sequence[T]) -> T: ...
```

### Bounded generics

```python
def clamp[T: (int, float)](value: T, low: T, high: T) -> T:
    return max(low, min(high, value))
```

### Generic classes

```python
class Stack[T]:
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()
```

## Protocol (Structural Typing)

Define interfaces based on structure, not inheritance:

```python
from typing import Protocol

class Renderable(Protocol):
    def render(self) -> str: ...

class Widget:
    def render(self) -> str:
        return "<widget/>"

def display(item: Renderable) -> None:
    print(item.render())

display(Widget())  # Works — Widget satisfies Renderable structurally
```

### Runtime-checkable protocols

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Sized(Protocol):
    def __len__(self) -> int: ...

assert isinstance([1, 2, 3], Sized)  # True at runtime
```

Use `@runtime_checkable` sparingly — prefer static checking.

### Generic protocols

```python
class Repository[T](Protocol):
    def get(self, id: int) -> T | None: ...
    def save(self, entity: T) -> None: ...
    def delete(self, id: int) -> None: ...
```

## Self Type

Use `Self` for methods returning the instance type, especially in class hierarchies:

```python
from typing import Self

class Builder:
    def with_name(self, name: str) -> Self:
        self._name = name
        return self

    @classmethod
    def create(cls) -> Self:
        return cls()
```

## TypeGuard and TypeIs

### TypeGuard (3.10+)

Narrow types in conditional branches:

```python
from typing import TypeGuard

def is_str_list(val: list[object]) -> TypeGuard[list[str]]:
    return all(isinstance(item, str) for item in val)

def process(data: list[object]) -> None:
    if is_str_list(data):
        # data is now list[str]
        print(", ".join(data))
```

### TypeIs (3.13+; `typing_extensions.TypeIs` on 3.12)

Stricter narrowing — narrows in both branches. `typing.TypeIs` was added by PEP 742 in
Python 3.13, so on a 3.12 target `from typing import TypeIs` raises `ImportError` and
`TypeGuard` is the only stdlib option:

```python
from typing import TypeIs

def is_positive_int(val: int | str) -> TypeIs[int]:
    return isinstance(val, int) and val > 0

def handle(val: int | str) -> None:
    if is_positive_int(val):
        # val is int
        print(val + 1)
    else:
        # val is str (narrowed in else branch too)
        print(val.upper())
```

Prefer `TypeIs` when the project targets 3.13+ — it provides stronger guarantees.
Otherwise use `TypeGuard`.

## Overload

Define multiple signatures for a function:

```python
from typing import overload

@overload
def get(key: str) -> str: ...
@overload
def get(key: str, default: int) -> str | int: ...

def get(key: str, default: int | None = None) -> str | int:
    value = lookup(key)
    if value is None and default is not None:
        return default
    return value
```

Use `@overload` when the return type varies based on argument types or counts.

## ParamSpec

Preserve function signatures through decorators:

```python
from collections.abc import Callable
from functools import wraps

def logged[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper
```

Declare the ParamSpec inline in the parameter list (`[**P, R]`), which is the 3.12+
idiom. There is no `type` alias form for a ParamSpec: the `type` statement builds a
`TypeAliasType`, so `type P = ParamSpec("P")` leaves `P.args` / `P.kwargs` undefined
and type checkers reject the resulting `Callable[P, R]`. When a ParamSpec must be
declared separately (to share it across functions), use `P = ParamSpec("P")` — a plain
assignment, no `type` keyword.

## Callable Types

```python
# Simple callable
type Callback = Callable[[str, int], None]

# Callable with ParamSpec (preserves full signature)
type Decorator[**P, R] = Callable[[Callable[P, R]], Callable[P, R]]

# Callable with no arguments
type Factory[T] = Callable[[], T]
```

## Common Patterns

### Optional fields with defaults

```python
@dataclass
class Config:
    host: str
    port: int = 8080
    debug: bool = False
    tags: list[str] = field(default_factory=list)
```

### TypedDict for structured dicts

```python
from typing import TypedDict, NotRequired

class UserPayload(TypedDict):
    name: str
    email: str
    age: NotRequired[int]
```

### Literal types

```python
from typing import Literal

type Direction = Literal["north", "south", "east", "west"]
type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

def set_level(level: LogLevel) -> None: ...
```

### Never type

```python
from typing import Never

def unreachable(value: Never) -> Never:
    raise AssertionError(f"Unexpected value: {value}")
```

Use `Never` for exhaustiveness checks:

```python
match status:
    case "active":
        ...
    case "inactive":
        ...
    case _ as unreached:
        unreachable(unreached)  # Type error if cases are not exhaustive
```

## Rules Summary

1. Always annotate function signatures (parameters and return type).
2. Use built-in generics (`list`, `dict`, `tuple`, `set`), never the deprecated `typing`
   aliases (`List`, `Dict`, `Tuple`, `Set`).
3. Use `X | None` instead of `Optional[X]`.
4. Use `type` statement for all type aliases.
5. Use `[T]` syntax for generic functions and classes, not explicit `TypeVar`.
6. Prefer `Protocol` over `ABC` when only method signatures matter.
7. Use `@override` on every overriding method.
8. Use `Self` for fluent interfaces and `@classmethod` return types.
9. Prefer `TypeIs` when targeting 3.13+; otherwise use `TypeGuard`.
10. Annotate every function signature, including `__init__(...) -> None`.
