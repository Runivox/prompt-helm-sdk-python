# Changelog

All notable changes to `prompt-helm` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
