# QA Self-Hosted Runner Auto-Update

Rebuild the local QA Docker instance (`127.0.0.1:28081`) automatically when dependency-related files merge to `main`.

## What runs

Workflow: [`.github/workflows/qa-auto-update.yml`](../../.github/workflows/qa-auto-update.yml)

Triggers on `push` to `main` when any of these change:

- `Dockerfile`
- `docker-compose.yml`
- `pyproject.toml`
- `apps/web/package.json`
- `apps/web/package-lock.json`
- `.github/dependabot.yml`

The job runs only on a self-hosted runner labeled **`ffos-qa`** and executes [`scripts/qa_deploy.sh`](../../scripts/qa_deploy.sh), which:

1. Stops a legacy `dillon-qa` compose project if it is still bound to port 28081
2. Runs `make qa-up` (rebuild + recreate `ffos-qa`)
3. Polls `http://127.0.0.1:28081/api/status` until `app_env` is `qa`

Personal mode on port 28080 is never touched.

## One-time Mac setup

Prerequisites on the machine that hosts QA:

- Docker Desktop running
- [`gh`](https://cli.github.com/) authenticated to `mlddragon`
- Repo cloned locally (runner workspace uses GitHub checkout; Docker bind mounts use your normal `~/FamilyFinanceOS_QA_Data`)

### 1. Install the self-hosted runner

From a current clone of this repo:

```bash
chmod +x scripts/install_qa_runner.sh scripts/qa_deploy.sh
./scripts/install_qa_runner.sh
```

Defaults:

- Runner directory: `~/.ffos/actions-runner`
- Runner name: `ffos-qa-mac`
- Labels: `self-hosted`, `macOS`, `ffos-qa`

The script registers the runner, installs a launchd service, and starts it. You may be prompted for your password when the service is installed.

Verify in GitHub: **Settings → Actions → Runners**. The runner should show **Idle** with labels including `ffos-qa`.

### 2. Merge the workflow to `main`

After the workflow file is on `main`, dependency merges (including Dependabot) will queue **QA auto-update** on this machine.

### 3. Smoke test manually

Before relying on automation:

```bash
make qa-update
curl -s http://127.0.0.1:28081/api/status
```

Expected: JSON with `"app_env":"qa"` and `"dataset_kind":"synthetic"`.

## Day-two operations

Restart the runner service:

```bash
cd ~/.ffos/actions-runner
./svc.sh stop
./svc.sh start
```

Remove the runner (also remove it in GitHub **Settings → Actions → Runners**):

```bash
cd ~/.ffos/actions-runner
./svc.sh stop
./svc.sh uninstall
./config.sh remove --token "$(gh api --method POST repos/mlddragon/family-finance-os/actions/runners/remove-token --jq .token)"
```

Re-register after OS upgrade or runner corruption:

```bash
rm -rf ~/.ffos/actions-runner/.runner
./scripts/install_qa_runner.sh
```

## Security notes

- Use a **repo-scoped** self-hosted runner for this repository only.
- Do not run untrusted fork PR workflows on this runner. The workflow is limited to `push` on `main` in `mlddragon/family-finance-os`.
- The job needs Docker access and read access to the repo checkout only; it does not push commits or publish artifacts.
- QA data stays in `~/FamilyFinanceOS_QA_Data` (external to git). Rebuilds preserve that data root.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Workflow queued forever | Runner offline or missing `ffos-qa` label | Start Docker Desktop; `./svc.sh start` in runner dir |
| Port 28081 bind error | Legacy `dillon-qa` container | `docker compose -p dillon-qa down --remove-orphans` |
| Health check timeout | Docker build failed | Check Actions job log; run `make qa-up` locally |
| Runner cannot pull image | Docker Desktop stopped | Start Docker Desktop before runner service |

## Related commands

```bash
make qa-up      # rebuild QA only (same as deploy without health wait script)
make qa-update  # rebuild QA + health check (local equivalent of the workflow)
make qa-down    # stop QA compose project
```
