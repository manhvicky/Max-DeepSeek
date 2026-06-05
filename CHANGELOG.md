# Changelog

## [Unreleased]

### Planned for v1.0.1
- Add richer README assets and onboarding notes
- Add GitHub Actions build-check
- Tighten public-facing docs and known limitations

## [1.0.0] - 2026-06-05

### Added
- FastAPI gateway compatible with OpenAI `/v1/models` and `/v1/chat/completions`
- Vietnamese React/Vite admin dashboard for accounts, API keys, logs, config and proxy management
- In-app update center, release metadata and maintainer info pages
- Smoke test and basic API regression script

### Security / Operations
- Configurable CORS allowlist
- Expiring admin JWT
- Masked and hashed API key storage for safer public defaults
- Docker-based deployment flow with update and rollback scripts
