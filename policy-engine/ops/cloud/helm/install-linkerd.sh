#!/usr/bin/env bash
set -euo pipefail

LINKERD_VERSION="${LINKERD_VERSION:-stable-2.15.2}"
LINKERD_CLI_BIN="${LINKERD_CLI_BIN:-$HOME/.linkerd2/bin}"
SPIRE_TRUST_BUNDLE="${SPIRE_TRUST_BUNDLE:-/etc/spire/trust-bundle.pem}"
SPIRE_ISSUER_CERT="${SPIRE_ISSUER_CERT:-/etc/spire/svid-cert.pem}"
SPIRE_ISSUER_KEY="${SPIRE_ISSUER_KEY:-/etc/spire/svid-key.pem}"

echo "Installing Linkerd CLI (${LINKERD_VERSION})"
curl -fsSL "https://run.linkerd.io/install-edge" | LINKERD2_VERSION="${LINKERD_VERSION}" sh
export PATH="${LINKERD_CLI_BIN}:${PATH}"

echo "Installing Linkerd CRDs"
linkerd install --crds | kubectl apply -f -

echo "Installing Linkerd control plane (SPIRE trust anchor mode)"
linkerd install \
  --identity-trust-anchors-file="${SPIRE_TRUST_BUNDLE}" \
  --identity-issuer-certificate-file="${SPIRE_ISSUER_CERT}" \
  --identity-issuer-key-file="${SPIRE_ISSUER_KEY}" \
  --set proxyInit.closeWaitTimeoutSecs=120 \
  --set proxy.cores=1 \
  --set proxy.memory.request=20Mi \
  --set proxy.memory.limit=64Mi \
  --set proxy.cpu.request=10m \
  --set proxy.cpu.limit=200m |
  kubectl apply -f -

echo "Installing Linkerd Viz extension"
linkerd viz install | kubectl apply -f -

echo "Linkerd installation completed"
