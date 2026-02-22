# Idiomatic Python Patterns Reference

## Protocols over ABCs

Prefer `Protocol` for defining interfaces when only structural compatibility is needed. Use `ABC` only when shared implementation (methods, state) must be inherited.

### Protocol — structural interface

```python
from typing import Protocol

class Serializable(Protocol):
    def to_dict(self) -> dict[str, object]: ...

class User:
    def to_dict(self) -> dict[str, object]:
        return {"name": self.name}

def save(obj: Serializable) -> None:
    data = obj.to_dict()  # User works — no inheritance needed
```

### ABC — shared implementation

```python
from abc import ABC, abstractmethod

class BaseProcessor(ABC):
    def run(self) -> None:
        data = self.fetch()
        result = self.process(data)
        self.store(result)

    @abstractmethod
    def fetch(self) -> bytes: ...

    @abstractmethod
    def process(self, data: bytes) -> dict: ...

    @abstractmethod
    def store(self, result: dict) -> None: ...
```

Use ABC when subclasses genuinely need shared logic (template method pattern). Use Protocol everywhere else.

## Enums

### Basic enum

```python
from enum import Enum, auto

class Status(Enum):
    PENDING = auto()
    ACTIVE = auto()
    ARCHIVED = auto()
```

### String enum (3.11+)

```python
from enum import StrEnum, auto

class Color(StrEnum):
    RED = auto()      # "red"
    GREEN = auto()    # "green"
    BLUE = auto()     # "blue"
```

`StrEnum` values are lowercase strings by default. Use for values that will be serialized to/from strings.

### Enum with methods

```python
class Permission(Enum):
    READ = 1
    WRITE = 2
    ADMIN = 4

    def includes(self, other: "Permission") -> bool:
        return self.value & other.value == other.value
```

### Enum in match/case

```python
match user.status:
    case Status.PENDING:
        send_reminder(user)
    case Status.ACTIVE:
        grant_access(user)
    case Status.ARCHIVED:
        deny_access(user)
```

## Context Managers

### Using `contextlib.contextmanager`

```python
from contextlib import contextmanager

@contextmanager
def temporary_directory():
    path = Path(tempfile.mkdtemp())
    try:
        yield path
    finally:
        shutil.rmtree(path)
```

### Class-based context manager

```python
class DatabaseTransaction:
    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    def __enter__(self) -> Cursor:
        self._cursor = self._conn.cursor()
        self._cursor.execute("BEGIN")
        return self._cursor

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        if exc_type is None:
            self._cursor.execute("COMMIT")
        else:
            self._cursor.execute("ROLLBACK")
        self._cursor.close()
        return False  # Do not suppress exceptions
```

### Async context manager

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def managed_connection(url: str):
    conn = await connect(url)
    try:
        yield conn
    finally:
        await conn.close()
```

### Composing context managers

```python
from contextlib import ExitStack

with ExitStack() as stack:
    files = [stack.enter_context(open(f)) for f in filenames]
    process_files(files)
```

## Generators and Iterators

### Generator functions

```python
def chunk[T](items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
```

### Generator expressions vs list comprehensions

```python
# Generator — lazy, memory efficient (use when only iterating)
total = sum(item.price for item in cart)

# List comprehension — eager (use when result is stored or reused)
prices = [item.price for item in cart]
```

### `yield from` for delegation

```python
def flatten[T](nested: Iterable[Iterable[T]]) -> Iterator[T]:
    for inner in nested:
        yield from inner
```

### Iterator protocol

```python
class CountDown:
    def __init__(self, start: int) -> None:
        self._current = start

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> int:
        if self._current <= 0:
            raise StopIteration
        self._current -= 1
        return self._current + 1
```

## Pathlib

Always use `pathlib.Path` for file system operations:

```python
from pathlib import Path

# Construction
config_dir = Path.home() / ".config" / "myapp"
data_file = config_dir / "data.json"

# Common operations
data_file.exists()
data_file.is_file()
data_file.parent.mkdir(parents=True, exist_ok=True)
content = data_file.read_text(encoding="utf-8")
data_file.write_text(json.dumps(data), encoding="utf-8")

# Globbing
for py_file in Path("src").rglob("*.py"):
    process(py_file)

# Parts
data_file.stem       # "data"
data_file.suffix     # ".json"
data_file.name       # "data.json"
data_file.parent     # Path(".config/myapp")
```

Always pass `encoding="utf-8"` to `read_text()` / `write_text()` / `open()`.

## Dataclass Patterns

### Immutable value object

```python
@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = "USD"

    def __add__(self, other: Self) -> Self:
        if self.currency != other.currency:
            raise ValueError("Currency mismatch")
        return type(self)(self.amount + other.amount, self.currency)
```

### Keyword-only fields

```python
@dataclass(kw_only=True, slots=True)
class SearchQuery:
    text: str
    limit: int = 10
    offset: int = 0
    include_archived: bool = False
```

### Post-init validation

```python
@dataclass(slots=True)
class Port:
    number: int

    def __post_init__(self) -> None:
        if not (0 <= self.number <= 65535):
            raise ValueError(f"Invalid port: {self.number}")
```

### Field with computed default

```python
@dataclass
class Request:
    url: str
    timestamp: float = field(default_factory=time.time)
    headers: dict[str, str] = field(default_factory=dict)
```

## Properties

```python
class Temperature:
    def __init__(self, celsius: float) -> None:
        self._celsius = celsius

    @property
    def celsius(self) -> float:
        return self._celsius

    @celsius.setter
    def celsius(self, value: float) -> None:
        if value < -273.15:
            raise ValueError("Below absolute zero")
        self._celsius = value

    @property
    def fahrenheit(self) -> float:
        return self._celsius * 9 / 5 + 32
```

Use properties when:
- Validation is needed on attribute assignment
- A derived value should look like a simple attribute
- Migrating from a public attribute to computed access without breaking API

## Slots

Use `__slots__` for classes with many instances or performance-critical paths:

```python
class Point:
    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
```

Benefits:
- Lower memory usage per instance
- Faster attribute access
- Prevents accidental attribute creation

Prefer `@dataclass(slots=True)` over manual `__slots__` when using dataclasses.

## Dunder Methods

### Essential dunders

```python
class Vector:
    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"Vector({self.x!r}, {self.y!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __add__(self, other: Self) -> Self:
        return type(self)(self.x + other.x, self.y + other.y)

    def __bool__(self) -> bool:
        return self.x != 0 or self.y != 0
```

Rules:
- Always implement `__repr__` for debuggability.
- Return `NotImplemented` (not `raise`) from comparison dunders for unsupported types.
- If `__eq__` is defined, also define `__hash__` (or set `__hash__ = None` for unhashable).
- Use `type(self)(...)` instead of `ClassName(...)` to support subclassing.

## String Handling

```python
# f-strings for all formatting
name = f"{first} {last}"
debug = f"{value = }"
padded = f"{score:>10.2f}"

# Multiline strings
query = (
    "SELECT id, name "
    "FROM users "
    "WHERE active = true"
)

# Join for sequences
csv_line = ", ".join(str(v) for v in values)

# Always specify encoding
with open(path, encoding="utf-8") as f:
    ...
```

## Guard Clauses

Prefer early returns over deeply nested conditions:

```python
# Preferred — guard clauses
def process_order(order: Order) -> Receipt:
    if order.is_cancelled:
        raise OrderError("Cancelled")
    if not order.items:
        raise OrderError("Empty order")
    if order.total <= 0:
        raise OrderError("Invalid total")

    return create_receipt(order)

# Avoid — nested conditions
def process_order(order: Order) -> Receipt:
    if not order.is_cancelled:
        if order.items:
            if order.total > 0:
                return create_receipt(order)
            else:
                raise OrderError("Invalid total")
        else:
            raise OrderError("Empty order")
    else:
        raise OrderError("Cancelled")
```
