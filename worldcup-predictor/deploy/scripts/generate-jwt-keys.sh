#!/usr/bin/env bash
# Generate the RSA-2048 key pair the Java service uses to sign / verify JWTs.
# Idempotent: re-running on an existing pair is a no-op so docker-compose
# bring-ups don't churn keys (which would invalidate every issued token).

set -euo pipefail

KEY_DIR="${1:-./deploy/jwt-keys}"
PRIVATE_KEY="${KEY_DIR}/jwt-private.pem"
PUBLIC_KEY="${KEY_DIR}/jwt-public.pem"

mkdir -p "${KEY_DIR}"

if [[ -f "${PRIVATE_KEY}" && -f "${PUBLIC_KEY}" ]]; then
    echo "JWT keys already present at ${KEY_DIR}; skipping generation."
    exit 0
fi

echo "Generating RSA-2048 key pair at ${KEY_DIR}..."
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "${PRIVATE_KEY}"
openssl pkey -in "${PRIVATE_KEY}" -pubout -out "${PUBLIC_KEY}"
chmod 600 "${PRIVATE_KEY}"
chmod 644 "${PUBLIC_KEY}"
echo "OK: keys written."
