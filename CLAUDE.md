# CLAUDE.md

Guidance for AI-assisted work on `site-calc-investment`, the public Python client and MCP server for the Site-Calc investment planning service.

## Setup and checks

```bash
uv venv && uv sync --extra dev
uv run pytest tests/ --ignore=tests/test_production.py --ignore=tests/test_mcp/test_mcp_production.py
uv run ruff check --fix . && uv run ruff format .
```

Production tests need `INVESTMENT_API_URL` and `INVESTMENT_API_KEY` and run against the live service.

## This package is public

Describe behavior, never the service's internals. Docs, field descriptions, docstrings, examples, tests, and commit messages must not mention how the optimization is solved or what runs behind the API. Version numbers refer to this package and to the service API version only.

## Review rule: read it as the user first

The audience is an engineer, or an LLM driving the MCP tools, who wants to model something specific and has only this package to go on: README, `docs/`, field descriptions, `get_device_schema` output, examples, and error messages.

Every change that touches models, MCP tool text or schemas, docs, examples, or error messages must be reviewed in this order:

1. From the public surfaces alone, write down how a first-time reader would build the feature in each form (Python API, MCP tools, any shortcut device), what each field means, which values are valid, what appears in results. Try the plausible mistakes (field on the wrong device, placeholder values, name collisions, combining two forms) and record what the package tells the reader.
2. Only then read the implementation and check every conclusion against it.
3. A place where the reader would build the wrong thing, or would learn of a mistake only at submit time instead of at input time, blocks the change. Field descriptions describe what a user should do; they never advertise corners the code merely tolerates.

Keep `docs/INVESTMENT_CLIENT_SPEC.md`, `docs/MCP_SERVER_SPEC.md`, the `get_device_schema` entries, and the Pydantic field descriptions saying the same thing.
