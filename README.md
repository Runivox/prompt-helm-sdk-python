# prompt-helm

> Official Python SDK for [PromptHelm](https://prompthelm.app) — call your managed prompts from any Python application with full typing, streaming, and retry support.

`prompt-helm` is a thin, dependency-light client for the PromptHelm gateway. It mirrors the behaviour of the official [Node SDK](https://github.com/Runivox/prompt-helm-sdk-node) so the contract is identical across both runtimes: same auth, same request shape, same error envelope, same SSE event types.

## Install

```bash
pip install prompt-helm
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
| `user_agent`    | `str \| None`              | `None`                          | Optional prefix for the SDK `User-Agent`, e.g. `"my-checkout-service/1.4.2"`.                       |
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
    ...  # everything else: err.status_code, err.code, err.correlation_id
```

The `correlation_id` on every error matches the `x-correlation-id` header recorded in PromptHelm logs — include it in any support request.

## API reference

### `PromptHelm` / `AsyncPromptHelm`

- `execute(*, prompt_slug=None, prompt_id=None, variables=None, system=None, user=None, model=None, temperature=None, max_tokens=None, top_p=None, stop_sequences=None, environment=None, timeout_ms=None) -> ExecuteResponse`
- `stream(...)` — same kwargs, returns an iterator (sync) or async iterator (async) of `StreamEvent`.
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
