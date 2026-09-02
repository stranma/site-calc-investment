# CLAUDE.md

Guidance for AI-assisted work on `site-calc-investment`, the public Python client for the Site-Calc investment planning service. The Python client library is the product; the MCP server in `site_calc_investment/mcp/` is a secondary add-on for LLM-driven use.

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

The audience is an engineer who wants to model something specific with the Python client and has only this package to go on: model field descriptions and docstrings, README, `docs/`, examples, and error messages. LLMs driving the MCP tools are a secondary audience.

Every change that touches models, docs, examples, error messages, or MCP tool text or schemas must be reviewed in this order:

1. From the public surfaces alone, write down how a first-time reader would build the feature with the Python client (including any shortcut device), what each field means, which values are valid, what appears in results. Try the plausible mistakes (field on the wrong device, placeholder values, name collisions, combining two forms) and record what the package tells the reader. Then do the same for the MCP path, briefly.
2. Only then read the implementation and check every conclusion against it.
3. A place where a Python-client reader would build the wrong thing, or would learn of a mistake only at submit time instead of at construction time, blocks the change. MCP hazards are reported and fixed when cheap. Field descriptions describe what a user should do; they never advertise corners the code merely tolerates.

Keep the Pydantic field descriptions, `docs/INVESTMENT_CLIENT_SPEC.md`, the examples, `docs/MCP_SERVER_SPEC.md`, and the `get_device_schema` entries saying the same thing.
