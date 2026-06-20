# Core layer

- `config.py`: all backend, data, runtime, and model paths.
- `schemas.py`: shared Pydantic response contracts.
- `storage.py`: case identifiers, atomic staging, and manifest persistence.

Core modules must not import API routers or model implementations.
