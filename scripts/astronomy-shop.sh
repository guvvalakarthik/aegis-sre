#!/usr/bin/env bash
set -Eeuo pipefail

cluster_name="aegis-lab"
namespace="aegis-lab"
release_name="astronomy-shop"
chart_version="0.42.6"
chart_repo="https://open-telemetry.github.io/opentelemetry-helm-charts"
chart_ref="opentelemetry-demo"
chart_values="infra/helm/values.yaml"
cluster_config="infra/kind/aegis-lab.yaml"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_tools() {
  require_command docker
  require_command kind
  require_command kubectl
  require_command helm
}

create_cluster() {
  require_tools
  if kind get clusters | grep -Fxq "$cluster_name"; then
    echo "Cluster $cluster_name already exists; leaving it unchanged."
    return
  fi
  kind create cluster --config "$cluster_config" --wait 5m
}

deploy() {
  require_tools
  kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -
  helm repo add opentelemetry "$chart_repo" --force-update
  helm repo update
  helm upgrade --install "$release_name" "$chart_ref"     --repo "$chart_repo"     --version "$chart_version"     --namespace "$namespace"     --values "$chart_values"     --atomic     --wait     --timeout 15m
}

verify() {
  require_tools
  test "$(kubectl config current-context)" = "kind-$cluster_name" || {
    echo "Refusing verification: current context is not kind-$cluster_name" >&2
    exit 1
  }
  kubectl -n "$namespace" get pods -o wide
  kubectl -n "$namespace" wait --for=condition=Available deployment --all --timeout=15m
  count="$(kubectl -n "$namespace" get deployment --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  test "$count" -ge 12 || {
    echo "Expected at least 12 deployments, found $count" >&2
    exit 1
  }
  echo "Verified $count available workload deployments."
}

forward() {
  require_tools
  test "$(kubectl config current-context)" = "kind-$cluster_name" || {
    echo "Refusing port-forward: current context is not kind-$cluster_name" >&2
    exit 1
  }
  kubectl -n "$namespace" port-forward svc/"$release_name-frontendproxy" 8080:8080
}

destroy() {
  require_tools
  if kind get clusters | grep -Fxq "$cluster_name"; then
    kind delete cluster --name "$cluster_name"
  else
    echo "Cluster $cluster_name does not exist; nothing to destroy."
  fi
}

case "${1:-}" in
  create) create_cluster ;;
  deploy) deploy ;;
  verify) verify ;;
  forward) forward ;;
  destroy) destroy ;;
  *)
    echo "Usage: $0 {create|deploy|verify|forward|destroy}" >&2
    exit 2
    ;;
esac
