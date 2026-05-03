#!/usr/bin/env bash
# scale_for_match_day.sh — pre-match horizontal scale-out (Phase 5, design §6.3).
#
# Usage:
#   ./scale_for_match_day.sh <namespace> <up|down>
#
# `up`   : scale every user-facing service to the high-traffic profile and
#          warm the Redis cache for today's predictions.
# `down` : revert to baseline.
#
# All numeric profiles come from the design table §6.3. Edit there first, then
# update this script — never the other way around.

set -euo pipefail

NAMESPACE="${1:-wcp-production}"
DIRECTION="${2:-up}"

if [[ "$DIRECTION" == "up" ]]; then
  FRONTEND=8
  JAVA_API=10
  ML_API=6
elif [[ "$DIRECTION" == "down" ]]; then
  FRONTEND=2
  JAVA_API=2
  ML_API=2
else
  echo "Usage: $0 <namespace> <up|down>" >&2
  exit 64
fi

echo "→ scaling namespace=$NAMESPACE direction=$DIRECTION"
kubectl -n "$NAMESPACE" scale deploy/wcp-frontend  --replicas="$FRONTEND"
kubectl -n "$NAMESPACE" scale deploy/wcp-java-api  --replicas="$JAVA_API"
kubectl -n "$NAMESPACE" scale deploy/wcp-ml-api    --replicas="$ML_API"

if [[ "$DIRECTION" == "up" ]]; then
  echo "→ warming Redis cache for today's predictions"
  POD=$(kubectl -n "$NAMESPACE" get pod -l app.kubernetes.io/name=wcp-ml-api -o jsonpath='{.items[0].metadata.name}')
  kubectl -n "$NAMESPACE" exec "$POD" -- python -c \
    "from src.services.cache import RedisCache; print('cache warm hook — implement in app')" \
    || echo "::warning ::cache warm hook not implemented yet"
fi

echo "✓ done"
