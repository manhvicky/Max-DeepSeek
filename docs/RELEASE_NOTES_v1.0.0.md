# Max-DeepSeek v1.0.0

First public release of Max-DeepSeek.

## Highlights

- Self-hosted OpenAI-compatible gateway backed by a DeepSeek account pool
- Vietnamese admin dashboard for accounts, API keys, logs, config and proxy management
- In-app update center with version check, changelog view, manual update command, rollback command and update history
- Author/maintainer metadata shown directly in dashboard
- Safer public-release defaults: masked+hashed API key storage, configurable CORS, expiring admin JWT
- Smoke test and basic API regression test included

## New in this release

- Added `Cap nhat` page in dashboard
- Added `Tac gia` page with maintainer info
- Added update APIs: status, check, apply, rollback, history
- Added `scripts/update.sh` and `scripts/rollback.sh`
- Added update manifest example for GitHub-hosted release metadata

## Validation

- `python3 -m compileall backend/app scripts tests`
- `cd web && npm run build`
- `docker build -f docker/Dockerfile -t max-deepseek:latest .`
- End-to-end API test on a clean container
- Smoke test on a clean container

## Maintainer

- Vu Duy Manh
- manhq7@gmail.com
