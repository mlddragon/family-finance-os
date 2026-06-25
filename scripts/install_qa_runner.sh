#!/usr/bin/env bash
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-mlddragon/family-finance-os}"
RUNNER_NAME="${RUNNER_NAME:-ffos-qa-mac}"
RUNNER_LABELS="${RUNNER_LABELS:-self-hosted,macOS,ffos-qa}"
RUNNER_DIR="${RUNNER_DIR:-${HOME}/.ffos/actions-runner}"
RUNNER_ARCH="$(uname -m)"

case "${RUNNER_ARCH}" in
  arm64) RUNNER_PACKAGE="actions-runner-osx-arm64" ;;
  x86_64) RUNNER_PACKAGE="actions-runner-osx-x64" ;;
  *)
    echo "Unsupported macOS architecture: ${RUNNER_ARCH}" >&2
    exit 1
    ;;
esac

if [[ -z "${GITHUB_RUNNER_TOKEN:-}" ]]; then
  echo "Fetching one-time runner registration token for ${REPO}..."
  GITHUB_RUNNER_TOKEN="$(
    gh api --method POST "repos/${REPO}/actions/runners/registration-token" --jq .token
  )"
fi

RUNNER_VERSION="${RUNNER_VERSION:-$(
  curl -fsSL https://api.github.com/repos/actions/runner/releases/latest |
    python3 -c "import sys, json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))"
)}"

RUNNER_TARBALL="${RUNNER_PACKAGE}-${RUNNER_VERSION}.tar.gz"
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_TARBALL}"

mkdir -p "${RUNNER_DIR}"
cd "${RUNNER_DIR}"

if [[ ! -f ./config.sh ]]; then
  echo "Downloading GitHub Actions runner ${RUNNER_VERSION} for ${RUNNER_ARCH}..."
  curl -fsSL -o "${RUNNER_TARBALL}" "${RUNNER_URL}"
  tar xzf "${RUNNER_TARBALL}"
  rm -f "${RUNNER_TARBALL}"
fi

if [[ ! -f ./.runner ]]; then
  echo "Configuring runner ${RUNNER_NAME} with labels: ${RUNNER_LABELS}"
  ./config.sh \
    --url "https://github.com/${REPO}" \
    --token "${GITHUB_RUNNER_TOKEN}" \
    --name "${RUNNER_NAME}" \
    --labels "${RUNNER_LABELS}" \
    --unattended \
    --replace
else
  echo "Runner already configured in ${RUNNER_DIR}; skipping config.sh."
fi

echo "Installing and starting runner service..."
./svc.sh install
./svc.sh start

echo "Runner ready. Verify in GitHub: Settings -> Actions -> Runners."
