# Python Project Structure Reference

## Directory Layout (src layout)

```
project-name/
├── pyproject.toml          # Single source of truth for metadata
├── README.md
├── LICENSE
├── src/
│   └── package_name/       # The importable package
│       ├── __init__.py      # Public API exports
│       ├── __main__.py      # Entry point for `python -m package_name`
│       ├── py.typed         # PEP 561 marker for typed package
│       ├── core/            # Core business logic
│       │   ├── __init__.py
│       │   └── ...
│       ├── models/          # Data models and types
│       │   ├── __init__.py
│       │   └── ...
│       └── utils/           # Internal utilities
│           ├── __init__.py
│           └── ...
├── tests/
│   ├── conftest.py          # Shared fixtures
│   ├── unit/
│   │   └── ...
│   └── integration/
│       └── ...
└── scripts/                 # Development and operational scripts
    └── ...
```

## Why src Layout

The `src/` layout prevents a class of bugs where the package in the working directory shadows the installed package. Without it, running `python` from the project root imports the local directory instead of the installed package, leading to subtle test failures and import issues.

```
# Without src layout — dangerous
project/
├── mypackage/     # This gets imported instead of the installed one
│   └── ...
└── tests/
    └── test_foo.py  # `import mypackage` imports the local dir, not installed

# With src layout — safe
project/
├── src/
│   └── mypackage/  # Not directly importable from project root
└── tests/
    └── test_foo.py  # `import mypackage` always imports the installed one
```

## pyproject.toml

### Minimal configuration

```toml
[project]
name = "package-name"
version = "0.1.0"
description = "Short description of the project"
requires-python = ">=3.12"
license = "MIT"
authors = [
    { name = "Author Name", email = "author@example.com" },
]
dependencies = []

[project.optional-dependencies]
dev = [
    # linter, type checker, test runner of choice
]

[build-system]
requires = ["<build-backend>"]
build-backend = "<build-backend>.build"
```

### With entry points (CLI commands)

```toml
[project.scripts]
mycommand = "package_name.__main__:main"
```

### Tool configuration

Keep all tool configuration in `pyproject.toml` — avoid separate config files:

```toml
[tool.<linter>]
target-version = "py312"
line-length = 88

[tool.<type-checker>]
python_version = "3.12"
strict = true

[tool.<test-runner>.ini_options]
testpaths = ["tests"]
```

## Module Organization

### Organize by domain, not by role

```
# Preferred — by domain
src/package_name/
├── users/
│   ├── __init__.py
│   ├── models.py
│   ├── service.py
│   └── errors.py
├── orders/
│   ├── __init__.py
│   ├── models.py
│   ├── service.py
│   └── errors.py
└── shared/
    ├── __init__.py
    └── types.py

# Avoid — by technical role
src/package_name/
├── models/
│   ├── user.py
│   └── order.py
├── services/
│   ├── user_service.py
│   └── order_service.py
└── errors/
    ├── user_errors.py
    └── order_errors.py
```

Domain-based organization keeps related code together, reducing cross-directory navigation and making dependencies between features explicit.

### When flat is acceptable

For small packages (< 10 modules), a flat structure is fine:

```
src/package_name/
├── __init__.py
├── models.py
├── service.py
├── errors.py
└── utils.py
```

Introduce subdirectories only when a module grows beyond ~300 lines or when distinct domains emerge.

## `__init__.py` Patterns

### Public API definition

```python
# src/package_name/__init__.py
"""Package description."""

from package_name.models import User, Order
from package_name.errors import AppError, NotFoundError
from package_name.service import create_user, process_order

__all__ = [
    "User",
    "Order",
    "AppError",
    "NotFoundError",
    "create_user",
    "process_order",
]
```

### Rules for `__init__.py`

- Keep minimal — only re-export the public API.
- Always define `__all__` to declare the public surface.
- Do not put implementation code in `__init__.py`.
- Sub-packages should have their own `__init__.py` with their own `__all__`.
- Avoid circular imports by importing symbols, not modules (use `from .models import User`, not `from . import models`).

### Empty `__init__.py`

For internal sub-packages that have no public API to expose, an empty `__init__.py` is correct. Do not add unnecessary imports.

## `__main__.py` Entry Point

```python
# src/package_name/__main__.py
"""Entry point for `python -m package_name`."""

from package_name.cli import main

if __name__ == "__main__":
    main()
```

This enables:
- `python -m package_name` to run the application
- Clean separation between entry point and CLI logic

## py.typed Marker

Create an empty `py.typed` file in the package root to indicate PEP 561 compliance:

```bash
touch src/package_name/py.typed
```

This tells type checkers that the package ships inline type information.

## Test Organization

```
tests/
├── conftest.py              # Project-wide fixtures
├── unit/
│   ├── conftest.py          # Unit-specific fixtures
│   ├── test_models.py
│   └── test_service.py
└── integration/
    ├── conftest.py          # Integration-specific fixtures
    └── test_api.py
```

### Naming conventions

- Test files: `test_<module>.py`
- Test classes: `Test<ClassName>`
- Test functions: `test_<behavior_description>`
- Fixtures: descriptive noun (`user`, `db_connection`, `sample_data`)

### Test file mirroring

Mirror the source structure in tests:

```
src/package_name/users/service.py  →  tests/unit/users/test_service.py
src/package_name/orders/models.py  →  tests/unit/orders/test_models.py
```

## Constants and Configuration

### Constants module

```python
# src/package_name/constants.py
"""Application-wide constants."""

DEFAULT_TIMEOUT: int = 30
MAX_RETRIES: int = 3
SUPPORTED_FORMATS: frozenset[str] = frozenset({"json", "csv", "xml"})
```

### Environment-based configuration

```python
# src/package_name/config.py
"""Application configuration."""

from dataclasses import dataclass, field
from os import environ

@dataclass(frozen=True, slots=True)
class Config:
    host: str = "localhost"
    port: int = 8080
    debug: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            host=environ.get("APP_HOST", "localhost"),
            port=int(environ.get("APP_PORT", "8080")),
            debug=environ.get("APP_DEBUG", "").lower() == "true",
        )
```

## Import Conventions

### Order

1. Standard library imports
2. *(blank line)*
3. Third-party imports
4. *(blank line)*
5. Local application imports

```python
import json
import logging
from pathlib import Path

# Third-party imports (if any)

from package_name.models import User
from package_name.errors import NotFoundError
```

### Rules

- Use absolute imports for cross-package references.
- Use relative imports only within the same sub-package and only one level deep.
- Avoid wildcard imports (`from module import *`).
- Import symbols, not modules, when only specific names are needed.
- Use `from __future__ import annotations` only if supporting Python < 3.12 is required.
