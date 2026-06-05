# prompt-helm

> Official Python SDK for [PromptHelm](https://prompthelm.app) — call your managed prompts from any Python application with full typing, streaming, and retry support.

`prompt-helm` is a thin, dependency-light client for the PromptHelm gateway. It mirrors the behaviour of the official [Node SDK](https://github.com/Runivox/prompt-helm-sdk-node) so the contract is identical across both runtimes: same auth, same request shape, same error envelope, same SSE event types.

The SDK exposes exactly two operations, backed by the only two token-callable
gateway endpoints:

- `execute` → `POST /api/v1/gateway/execute`
- `stream` → `POST /api/v1/gateway/stream` (Server-Sent Events)

Authentication is `Authorization: Bearer phk_<token>`. The default base URL is
`https://api.prompthelm.app`. There are no token-callable prompt-fetch,
version-listing, or telemetry endpoints — a saved prompt is resolved by passing
`prompt_slug`/`prompt_id` (with an optional `environment`) into `execute`/`stream`.

## Install

```bash
pip install prompt-helm-sdk
```

The package ships strict type information (PEP 561 `py.typed`) and supports Python 3.9 through 3.13.

## Quickstart (sync)

```python
import os
from prompt_helm import PromptHelm

ph = PromptHelm(api_key=os.environ["PROMPTHELM_API_KEY"])

result = ph.execute(
    prompt_slug="welcome",
    variables={"name": "World"},
)

print(result.output)
print(f"{result.total_tokens} tokens, ${result.cost:.6f}, {result.latency_ms} ms")
```

## Quickstart (async)

```python
import asyncio
import os
from prompt_helm import AsyncPromptHelm

async def main() -> None:
    async with AsyncPromptHelm(api_key=os.environ["PROMPTHELM_API_KEY"]) as ph:
        result = await ph.execute(prompt_slug="welcome", variables={"name": "World"})
        print(result.output)

asyncio.run(main())
```

## Streaming

```python
for event in ph.stream(prompt_slug="welcome", variables={"name": "World"}):
    if event.type == "chunk":
        print(event.content, end="", flush=True)
    elif event.type == "done":
        print(f"\n[{event.total_tokens} tokens • ${event.cost:.6f}]")
```

The async equivalent uses `async for`:

```python
async with AsyncPromptHelm(api_key=os.environ["PROMPTHELM_API_KEY"]) as ph:
    async for event in ph.stream(prompt_slug="welcome"):
        if event.type == "chunk":
            print(event.content, end="", flush=True)
```

## Configuration

Both clients accept the same keyword arguments:

| Argument        | Type                       | Default                         | Description                                                                                          |
| --------------- | -------------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `api_key`       | `str`                      | _required_                      | Token that begins with `phk_` followed by 32 hex chars.                                              |
| `base_url`      | `str \| None`              | `https://api.prompthelm.app`    | Override for self-hosted / staging environments.                                                     |
| `timeout`       | `float \| None` (seconds)  | `60.0`                          | Per-request HTTP deadline. Stream requests share the same budget.                                    |
| `max_retries`   | `int \| None`              | `2`                             | Bounded retries for 5xx and transport errors. 4xx responses (including 429) are never retried.       |
| `user_agent`    | `str \| None`              | `None`                          | Optional prefix for the SDK `User-Agent` (`prompt-helm-sdk-python/<version>`), e.g. `"my-checkout-service/1.4.2"`. |
| `headers`       | `Mapping[str, str] \| None`| `None`                          | Extra headers to send on every request.                                                              |
| `http_client`   | `httpx.Client \| None`     | `None`                          | Bring your own `httpx` client (handy for shared connection pooling). The SDK will not close it.      |

## Errors

```python
from prompt_helm import (
    PromptHelm,
    PromptHelmError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ApiError,
    TimeoutError,
)

ph = PromptHelm(api_key="phk_<your-api-token>")

try:
    result = ph.execute(prompt_slug="welcome")
except AuthenticationError:
    ...  # 401 — rotate the key
except RateLimitError as err:
    ...  # 429 — back off; SDK never retries this for you
except TimeoutError as err:
    ...  # the configured client deadline elapsed
except PromptHelmError as err:
    ...  # everything else: err.status_code, err.error_code, err.message, err.request_id
```

Every `PromptHelmError` mirrors the server error envelope
(`{ statusCode, errorCode, message, timestamp, requestId }`) and exposes
`status_code`, `error_code`, `message`, and `request_id`. The `request_id`
matches the `X-Request-Id` recorded in PromptHelm logs — include it in any
support request.

## API reference

### `PromptHelm` / `AsyncPromptHelm`

- `execute(*, prompt_slug=None, prompt_id=None, variables=None, system=None, user=None, model=None, temperature=None, max_tokens=None, top_p=None, stop_sequences=None, environment=None, timeout_ms=None) -> ExecuteResponse`
- `stream(...)` — same kwargs, returns an iterator (sync) or async iterator (async) of `StreamEvent`.

`environment` accepts only `"production"` or `"development"`. When omitted, the
server resolves the latest version of the prompt.
- `close()` (sync) / `aclose()` (async) — release the underlying connection pool. Context managers do this for you.

### `ExecuteResponse`

Frozen dataclass: `id`, `output`, `model`, `input_tokens`, `output_tokens`, `total_tokens`, `latency_ms`, `cost`, `timestamp`.

### `StreamEvent`

Tagged union of `StreamChunkEvent` (`type="chunk"`, `content`), `StreamDoneEvent` (final usage / cost), and `StreamErrorEvent` (raised internally as `ApiError`).

## Development

```bash
pip install -e ".[dev]"
ruff check src tests
ruff format --check src tests
mypy --strict src
pytest -v
python -m build
```

## License

MIT — see [LICENSE](./LICENSE).
