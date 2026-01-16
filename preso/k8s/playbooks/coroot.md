# Coroot

Distributed tracing allows engineers to visualize the path of a request across all of these components, which can help identify performance bottlenecks, latency issues, and errors.

While most distributed tracing tools are good at visualizing individual request traces, many struggle to provide a comprehensive overview of system performance.

At Coroot, we've addressed this challenge by creating a new interface that allows you to easily explore and understand system performance with just a few clicks.


## Production-Grade Multi-Cluster Observability with Coroot  
## SRE Runbook – Multi-Cloud (OCI / AWS / Azure / GCP)

---

## 1. Purpose & Scope

This document defines a **production-grade SRE runbook** for deploying and operating **Coroot-based multi-cluster observability** with:

- Coroot eBPF-based telemetry
- Decentralized metrics & logs storage
- Global federation (read-only)
- Trading-grade SLOs
- Full alerting & incident lifecycle
- Log monitoring with actionable queries
- Cost, profiling, and risk monitoring

Target workloads: **Trading, FinTech, Payments, Regulated SaaS**

---

## 2. Core Design Principles

- Cluster autonomy (no global blast radius)
- Decentralized storage per cluster
- Global visibility without raw data centralization
- eBPF-first observability
- SLO-driven operations
- Private-by-default security posture

---

## 3. High-Level Architecture (Cloud-Agnostic)

```text
┌──────────────────────────────────────────────┐
│ Global Observability Plane                   │
│ ─────────────────────────────────────────── │
│ Coroot Global UI (Read-only)                 │
│ Prometheus Federation (derived metrics only) │
│ Global SLO & Incident Views                  │
│ Alert Routing (PD / Slack / Teams / Webhook) │
└───────────────┬─────────────────────────────┘
                │
┌───────────────┴─────────────────────────────┐
│ Per-Cluster Observability (Isolated)         │
│ ─────────────────────────────────────────── │
│ Coroot Server (HA)                           │
│ Prometheus / VictoriaMetrics                │
│ Loki / OpenSearch                            │
│ Alertmanager                                │
│ Object Storage (cloud-native)                │
│ Coroot Node Agent (eBPF)                     │
└─────────────────────────────────────────────┘
```

---

## 4. Coroot Node Agent (eBPF) – Mandatory

### Purpose
The Coroot Node Agent uses **eBPF** to collect:
- Kernel-level CPU, memory, disk, and network metrics
- Syscall latency and lock contention
- Network flows and retransmissions
- Application performance signals without code instrumentation

### Deployment

```bash
helm repo add coroot https://coroot.github.io/helm-charts

helm install coroot coroot/coroot \
  -n observability \
  --create-namespace \
  --set replicas=3 \
  --set persistence.enabled=true \
  --set persistence.size=100Gi \
  --set resources.requests.cpu=500m \
  --set resources.requests.memory=1Gi \
  --set ingress.enabled=true \
  --set ingress.className=oci \
  --set auth.enabled=true

helm install coroot-agent coroot/coroot-node-agent \
  -n observability-system \
  --create-namespace \
  --set ebpf.enabled=true \
  --set privileged=true

e
```

### Kernel Requirements
- Linux kernel ≥ 5.8
- cgroup v2 preferred
- BTF enabled
- seccomp profiles must allow eBPF syscalls

### SRE Validation
- Verify eBPF programs loaded
- Confirm per-node CPU flame graphs visible in Coroot UI
- Validate syscall latency metrics

---

## 5. Metrics Storage Strategy (Decentralized)

### Storage Tiers (Per Cluster)

| Tier | Technology | Retention | Purpose |
|----|----|----|----|
| Hot | Prometheus | 7–30 days | Fast RCA |
| Scaled | VictoriaMetrics | 30–90 days | High cardinality |
| Cold | Object Storage | 90–365 days | Audit & trends |

### Principles
- No shared metrics backend across clusters
- Each cluster owns its own data lifecycle
- Global plane consumes **derived metrics only**

---

## 6. Federation (Global – Read Only)

### What Is Federated
- Coroot-derived metrics
- SLO indicators
- Alert state metrics
- Topology summaries

### What Is NOT Federated
- Raw time-series samples
- Application logs
- High-cardinality labels

### Prometheus Federation Example

```yaml
scrape_configs:
- job_name: federate
  metrics_path: /federate
  honor_labels: true
  params:
    match[]:
      - '{__name__=~"coroot_.*|slo_.*|alert_.*"}'
```

---

## 7. Alerting & Incident Management

### Alert Sources
- Coroot anomaly detection
- Prometheus rule-based alerts
- SLO burn-rate alerts

### Alert Severity Model

| Severity | Action |
|-------|-------|
| Critical | PagerDuty P1 |
| High | Slack + Teams |
| Medium | Slack |
| Low | Dashboard only |

### Alertmanager Routing (Example)

```yaml
route:
  receiver: default
  routes:
  - matchers:
    - severity="critical"
    receiver: pagerduty
  - matchers:
    - severity="high"
    receiver: slack
  - matchers:
    - severity="medium"
    receiver: teams
```

### Integrations
- PagerDuty (P1/P2 incidents)
- Slack (SRE channels)
- Microsoft Teams (NOC)
- Webhooks (SOAR / automation)

---

## 8. SLOs (Trading-Grade)

### Golden Signals

| Signal | Objective |
|-----|-----|
| Availability | ≥ 99.99% |
| p99 Latency | < 10 ms |
| Error Rate | < 0.01% |
| Saturation | < 70% |

### Example SLO – Trade Execution Latency

```yaml
slo:
  name: trade_execution_latency
  service: trade-engine
  objective: 99.9
  indicator:
    latency:
      threshold: 10ms
```

### Derived Outputs
- Error budget
- Burn rate (1h / 6h / 24h)
- Automatic incident creation on fast burn

---

## 9. Log Monitoring & Queries

### Logging Stack
- Fluent Bit / Promtail (collection)
- Loki or OpenSearch (storage)
- JSON structured logs mandatory

### Example Application Log

```json
{
  "service": "trade-engine",
  "order_id": "OID-10021",
  "latency_ms": 14,
  "status": "REJECTED",
  "reason": "RISK_LIMIT"
}
```

### Log Queries (Examples)

**Rejected trades**
```logql
{service="trade-engine"} |= "REJECTED"
```

**High-latency executions**
```logql
{service="trade-engine"} | json | latency_ms > 10
```

**Risk violations**
```logql
|= "RISK_LIMIT"
```

**Correlation with incident window**
```logql
{service="trade-engine"} |~ "ERROR|REJECTED"
```

---

## 10. Incident Lifecycle (SRE)

```text
Signal Detected
 → Alert Fired
 → Coroot RCA Generated
 → SLO Burn Analysis
 → PagerDuty Incident
 → Slack / Teams War Room
 → Mitigation Applied
 → Recovery Confirmed
 → Postmortem & Action Items
```

### Coroot RCA Capabilities
- Dependency graph analysis
- Resource anomaly correlation
- Change detection (deployments/configs)
- Time-aligned metrics and logs

---

## 11. SRE Operational Checklist

- [ ] Coroot Server HA deployed
- [ ] Coroot Node Agent running on all nodes
- [ ] Metrics retention validated
- [ ] Federation tested (read-only)
- [ ] Alerts routed correctly
- [ ] SLO burn alerts verified
- [ ] Log queries validated during incident simulation

---

