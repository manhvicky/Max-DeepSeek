# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-06-01

First public release candidate.

### Added

- OpenAI-compatible endpoints for `/v1/models` and `/v1/chat/completions`
- Admin dashboard for account, key, config, proxy and log management
- Smoke test script at `scripts/smoke_test.py`
- Basic API regression test at `tests/test_api.py`
- `.env.example` and GitHub release checklist docs

### Changed

- Hardened CORS handling with environment-driven origins
- Added expiration to admin JWT tokens
- API keys are now stored in masked/hashed form for safer public releases
- Improved account UI with batch add flow and request-count visibility
- Refreshed README for self-hosted/public GitHub usage

### Notes

- Before tagging a real GitHub release, run the validation commands in `README.md` and `docs/RELEASE_CHECKLIST.md`.
