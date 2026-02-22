# Modern Python 3.12+ Syntax Reference

## Structural Pattern Matching

### Basic value matching

```python
match status_code:
    case 200:
        return "OK"
    case 301 | 302:
        return "Redirect"
    case 404:
        return "Not Found"
    case _:
        return "Unknown"
```

### Destructuring sequences

```python
match point:
    case (0, 0):
        print("Origin")
    case (x, 0):
        print(f"On x-axis at {x}")
    case (0, y):
        print(f"On y-axis at {y}")
    case (x, y):
        print(f"Point at ({x}, {y})")
```

### Destructuring mappings

```python
match event:
    case {"type": "click", "x": int(x), "y": int(y)}:
        handle_click(x, y)
    case {"type": "keypress", "key": str(key)} if key.isprintable():
        handle_key(key)
    case {"type": "resize", "width": w, "height": h} if w > 0 and h > 0:
        handle_resize(w, h)
```

### Class pattern matching

```python
match shape:
    case Circle(radius=r) if r > 0:
        area = math.pi * r ** 2
    case Rectangle(width=w, height=h):
        area = w * h
    case Triangle(base=b, height=h):
        area = 0.5 * b * h
```

### Nested patterns

```python
match config:
    case {"database": {"host": str(host), "port": int(port)}}:
        connect(host, port)
    case {"database": {"url": str(url)}}:
        connect_url(url)
```

### Guards

Use `if` guards for additional conditions that cannot be expressed structurally:

```python
match command:
    case Command(name="delete", target=t) if t != "/":
        delete(t)
    case Command(name="delete", target="/"):
        raise PermissionError("Cannot delete root")
```

### When to use match/case vs if/elif

Prefer `match`/`case` when:
- Destructuring data structures (dicts, tuples, dataclasses)
- Dispatching on type + structure simultaneously
- Multiple related conditions on the same value

Prefer `if`/`elif` when:
- Simple boolean conditions on unrelated expressions
- Only one or two branches
- Conditions are not structural (e.g., `x > 10 and y < 5`)

## The `type` Statement (3.12+)

### Basic type aliases

```python
type UserId = int
type Headers = dict[str, str]
type Callback = Callable[[str], None]
```

### Generic type aliases

```python
type Result[T] = T | Error
type Pair[A, B] = tuple[A, B]
type Matrix[T] = list[list[T]]
```

### With ParamSpec

```python
type Handler[**P] = Callable[P, Awaitable[None]]
type Decorator[**P, R] = Callable[[Callable[P, R]], Callable[P, R]]
```

### With TypeVarTuple

```python
type Shape[*Ts] = tuple[*Ts]
```

### Advantages over legacy TypeAlias

- Lazily evaluated — forward references work without quotes
- Supports inline generic parameters (no separate `TypeVar` declaration)
- Clear, dedicated syntax distinguishable from variable assignment

## Exception Groups (3.11+)

### Creating exception groups

```python
errors: list[ValueError] = []
for item in items:
    try:
        validate(item)
    except ValueError as e:
        errors.append(e)
if errors:
    raise ExceptionGroup("Validation failed", errors)
```

### Catching with `except*`

```python
try:
    process_batch(items)
except* ValueError as eg:
    for err in eg.exceptions:
        log_validation_error(err)
except* ConnectionError as eg:
    for err in eg.exceptions:
        retry_connection(err)
```

Multiple `except*` clauses can match the same `ExceptionGroup` — each handles a disjoint subset. This is different from regular `except` chains where only the first match runs.

### With asyncio.TaskGroup

```python
async def fetch_all(urls: list[str]) -> list[Response]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch(url)) for url in urls]
    return [t.result() for t in tasks]
```

If any task fails, `TaskGroup` raises an `ExceptionGroup` containing all failures.

## The `@override` Decorator (3.12+)

Mark methods that intentionally override a base class method. Type checkers will flag an error if the base method doesn't exist or the signature is incompatible.

```python
from typing import override

class Base:
    def process(self, data: str) -> None:
        ...

class Child(Base):
    @override
    def process(self, data: str) -> None:
        # Type checker ensures Base.process exists and signature matches
        ...
```

Always use `@override` when overriding. It catches:
- Typos in method names
- Accidental signature mismatches
- Base class API changes that silently break subclasses

## F-String Enhancements (3.12+)

### Nested quotes (3.12+)

```python
msg = f"User {user["name"]} has {len(user["items"])} items"
```

Prior to 3.12, nested quotes inside f-string expressions required alternating quote types. As of 3.12, reuse of the same quote type is allowed.

### Multi-line expressions

```python
result = f"Total: {
    sum(
        item.price * item.quantity
        for item in cart
    )
:.2f}"
```

### Debug format with `=`

```python
x = 42
print(f"{x = }")       # "x = 42"
print(f"{x * 2 = }")   # "x * 2 = 84"
```

## Walrus Operator (`:=`)

### In while loops

```python
while (chunk := file.read(8192)):
    process(chunk)
```

### In comprehensions

```python
results = [
    cleaned
    for raw in data
    if (cleaned := normalize(raw)) is not None
]
```

### In conditional expressions

```python
if (m := re.match(r"(\d+)-(\d+)", text)) is not None:
    start, end = int(m.group(1)), int(m.group(2))
```

Avoid overusing the walrus operator. Prefer it only when it eliminates a redundant computation or improves readability by keeping related logic together.
