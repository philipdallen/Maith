#!/usr/bin/env bash
# install_elan.sh — checksum-pinned elan install for CI.
#
# Why this exists (Maith #82). The previous bootstrap was
#   curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh
# which executes whatever the *mutable* `master` ref points at, with nothing
# verifying the content. A moved or compromised upstream ref would change what
# runs in CI silently. This downloads a *tagged release asset* and verifies its
# SHA-256 against a pinned digest before extracting, so the bytes that execute
# are the bytes that were reviewed.
#
# Ported from PleaNP tooling/install_elan.sh (PleaNP #136), same shape.
#
# Usage (from the repo root):
#   tooling/install_elan.sh
#
# Env overrides (for testing / upgrades):
#   ELAN_VERSION  release tag to fetch           (default: v4.2.4)
#   ELAN_SHA256   expected SHA-256 of the asset  (must match ELAN_VERSION)
#   ELAN_ASSET    release asset name             (default: linux x86_64)
#
# The default asset is `x86_64-unknown-linux-gnu`, matching GitHub's
# `ubuntu-latest` runners. Bump ELAN_VERSION and ELAN_SHA256 together — the
# digest comes from the release's `assets[].digest` field:
#   gh api repos/leanprover/elan/releases/tags/<version> \
#     --jq '.assets[] | select(.name=="elan-x86_64-unknown-linux-gnu.tar.gz") | .digest'
set -euo pipefail

ELAN_VERSION="${ELAN_VERSION:-v4.2.4}"
ELAN_ASSET="${ELAN_ASSET:-elan-x86_64-unknown-linux-gnu.tar.gz}"
ELAN_SHA256="${ELAN_SHA256:-42b94d4244e8353142c456ec0e4ca6528fd898a6c604d4059f494e706e431f63}"
URL="https://github.com/leanprover/elan/releases/download/${ELAN_VERSION}/${ELAN_ASSET}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "[install_elan] fetching ${ELAN_ASSET} ${ELAN_VERSION}"
curl --proto '=https' --tlsv1.2 -sSfL -o "$tmp/$ELAN_ASSET" "$URL"

echo "${ELAN_SHA256}  $tmp/$ELAN_ASSET" | sha256sum --check --status || {
  echo "[install_elan] SHA-256 mismatch for ${ELAN_ASSET} (${ELAN_VERSION})" >&2
  echo "[install_elan] expected ${ELAN_SHA256}" >&2
  echo "[install_elan] got      $(sha256sum "$tmp/$ELAN_ASSET" | cut -d' ' -f1)" >&2
  exit 1
}

tar -xzf "$tmp/$ELAN_ASSET" -C "$tmp"
"$tmp/elan-init" -y --default-toolchain none
echo "[install_elan] elan ${ELAN_VERSION} installed (digest verified)"
