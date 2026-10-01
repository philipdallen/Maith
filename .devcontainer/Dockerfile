# Maith devcontainer — persistent Lean 4 + Mathlib environment.
#
# Protocol ported from PleaNP (2026-09-15). Persistence comes from this image
# plus the community Mathlib olean cache (`lake exe cache get`), NOT from any
# live machine. Building Mathlib from source never happens here.
#
# The toolchain is pinned by lean-toolchain (v4.31.0); Mathlib by
# lakefile.lean (@ "v4.31.0"). Bump both together.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git python3 && \
    rm -rf /var/lib/apt/lists/*

# elan (Lean version manager) — matches repo CI exactly. Checksum-pinned (#82):
# no curl|sh — a tagged release asset is downloaded and its SHA-256 verified
# before extraction, so a moved/compromised `master` ref cannot change what runs.
# Bump ELAN_VERSION and ELAN_SHA256 together; digest from the release's
# `assets[].digest` field (see tooling/install_elan.sh for the query).
RUN ELAN_VERSION=v4.2.4 \
 && ELAN_ASSET=elan-x86_64-unknown-linux-gnu.tar.gz \
 && ELAN_SHA256=42b94d4244e8353142c456ec0e4ca6528fd898a6c604d4059f494e706e431f63 \
 && curl --proto '=https' --tlsv1.2 -sSfL -o /tmp/$ELAN_ASSET \
      "https://github.com/leanprover/elan/releases/download/$ELAN_VERSION/$ELAN_ASSET" \
 && echo "$ELAN_SHA256  /tmp/$ELAN_ASSET" | sha256sum --check --status \
 && tar -xzf /tmp/$ELAN_ASSET -C /tmp \
 && /tmp/elan-init -y --default-toolchain none \
 && rm -f /tmp/$ELAN_ASSET /tmp/elan-init \
 && /root/.elan/bin/elan --version

ENV PATH="/root/.elan/bin:${PATH}"

# Vanilla image: the repo is mounted at /workspaces/Maith by the devcontainer
# framework; `lake exe cache get` + `lake build` run in postCreateCommand (see
# devcontainer.json) so this image stays small and cache/distro-agnostic.