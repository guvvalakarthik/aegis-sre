#!/usr/bin/env bash
set -Eeuo pipefail

namespace="aegis-lab"
versions_file="infra/telemetry/versions.env"

test -f "$versions_file" || { echo "Missing $versions_file" >&2; exit 1; }
# shellcheck disable=SC1090
source "$versions_file"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

repos() {
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
  helm repo add grafana https://grafana.github.io/helm-charts --force-update
  helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts --force-update
  helm repo update
}

install_chart() {
  local release="$1" chart="$2" version="$3" values="$4"
  helm upgrade --install "$release" "$chart"     --version "$version"     --namespace "$namespace"     --values "$values"     --atomic     --wait     --timeout 15m
}

install() {
  require helm
  require kubectl
  kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -
  kubectl -n "$namespace" create secret generic grafana-admin     --from-literal=admin-user="${GRAFANA_ADMIN_USER:-admin}"     --from-literal=admin-password="${GRAFANA_ADMIN_PASSWORD:?Set GRAFANA_ADMIN_PASSWORD}"     --dry-run=client -o yaml | kubectl apply -f -
  repos
  install_chart "$PROMETHEUS_RELEASE" "prometheus-community/$PROMETHEUS_CHART" "$PROMETHEUS_VERSION" infra/telemetry/prometheus-values.yaml
  install_chart "$LOKI_RELEASE" "grafana/$LOKI_CHART" "$LOKI_VERSION" infra/telemetry/loki-values.yaml
  install_chart "$TEMPO_RELEASE" "grafana/$TEMPO_CHART" "$TEMPO_VERSION" infra/telemetry/tempo-values.yaml
  install_chart "$OTEL_RELEASE" "open-telemetry/$OTEL_CHART" "$OTEL_VERSION" infra/telemetry/otel-values.yaml
}

verify() {
  require kubectl
  kubectl -n "$namespace" get pods,svc,pvc
  kubectl -n "$namespace" wait --for=condition=Ready pod --all --timeout=15m
  kubectl -n "$namespace" get --raw /apis/apps/v1 | grep -q deployments
  echo "Telemetry stack resources are ready."
}

destroy() {
  require helm
  for release in "$OTEL_RELEASE" "$TEMPO_RELEASE" "$LOKI_RELEASE" "$PROMETHEUS_RELEASE"; do
    helm uninstall "$release" --namespace "$namespace" --ignore-not-found
  done
}

case "${1:-}" in
  install) install ;;
  verify) verify ;;
  destroy) destroy ;;
  *)
    echo "Usage: $0 {install|verify|destroy}" >&2
    exit 2
    ;;
esac
