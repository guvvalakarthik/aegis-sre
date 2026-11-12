# Kubernetes observability testbed

Issue #7 uses the upstream OpenTelemetry Astronomy Shop as an external Helm dependency.
The repository contains only the cluster configuration, values, lifecycle commands, and
validation documentation; it does not vendor upstream application code.

## Pinned inputs

| Input | Pin |
| --- | --- |
| kind | v0.28.0 or newer compatible with the pinned node image |
| Kubernetes node image | kindest/node:v1.32.5 with digest |
| Helm chart | opentelemetry-demo 0.42.6 |
| Demo application | 3.1.0, supplied by the chart |
| Cluster | aegis-lab |
| Namespace | aegis-lab |
| Release | astronomy-shop |

The chart is maintained by the OpenTelemetry project and is installed from its published
Helm repository.

## Lifecycle

From the repository root:

~~~bash
bash scripts/astronomy-shop.sh create
bash scripts/astronomy-shop.sh deploy
bash scripts/astronomy-shop.sh verify
bash scripts/astronomy-shop.sh forward
~~~

The frontend is available at http://localhost:8080 while port-forwarding is running.

To remove only the named test cluster:

~~~bash
bash scripts/astronomy-shop.sh destroy
~~~

The destroy action refuses to target any cluster other than aegis-lab.

## Resource and safety expectations

- Allocate at least 4 CPUs and 8 GiB memory to Docker for the full demo.
- Use a disposable kind cluster; never point these commands at a shared or production context.
- Helm deployment uses atomic install, readiness waits, and a bounded 15-minute timeout.
- The verifier requires the kind-aegis-lab context and at least 12 deployments.
- Capture Helm render output, kubectl availability output, and a browser smoke check as Issue #7 evidence.

## CI render check

CI should render the exact pinned chart without contacting a cluster:

~~~bash
helm repo add opentelemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update
helm template astronomy-shop opentelemetry/opentelemetry-demo \
  --version 0.42.6 \
  --namespace aegis-lab \
  --values infra/helm/values.yaml
~~~
