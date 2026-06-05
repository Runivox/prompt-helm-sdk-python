# Changelog

All notable changes to `prompt-helm` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Standardised the SDK `User-Agent` to `prompt-helm-sdk-python/<version>`, with
  the version resolved from installed package metadata.
- Error parsing now matches the server envelope
  `{ statusCode, errorCode, message, timestamp, requestId }` (and SSE
  `{ type:'error', errorCode, message, requestId }`). `PromptHelmError`
  instances now expose `status_code`, `error_code`, `message`, and `request_id`
  (previously `code` / `correlation_id`).
- `ErrorEnvelope` fields renamed to `error_code` / `request_id` / `timestamp`.
- README clarified to document the real token-callable surface
  (`execute` / `stream` only), env-var token usage, the
  `production`/`development` environment values, and the default base URL.

### Added

- CI dependency vulnerability audit via `pip-audit`.

## [0.1.0] - 2026-05-13

### Added

- Initial public release.
- `PromptHelm` synchronous client with `execute()` and `stream()` methods.
- `AsyncPromptHelm` asynchronous client with `execute()` and `stream()` methods.
- Bearer-token authentication and API key format validation (`phk_` + 32 hex).
- Server-Sent Events parser for streaming completions.
- Exponential backoff with jitter for retryable failures (5xx, network errors).
- Typed error hierarchy: `PromptHelmError`, `AuthenticationError`,
  `AuthorizationError`, `NotFoundError`, `RateLimitError`, `ApiError`,
  `TimeoutError`.
- Strict typing with `py.typed` marker (PEP 561).
