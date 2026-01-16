# Kyverno
Kyverno is a Kubernetes-native policy engine designed for platform engineering teams. It enables security, compliance, automation, and governance through policy-as-code

The policies here are maintained by the community and are as samples that demonstrate the power and flexibility of Kyverno. To use in your environment, make sure you test with the right versions of Kyverno and Kubernetes, and optimize for your use case.
Select the Policy Type and Policy Category on the left navigation, or use the search, to find the policy you need.
[List of Sample Policies](https://kyverno.io/policies/)

## Kyverno Production Kubernetes Policy Governance Framework (CIS Benchmark Aligned)

---

## 1. Overview

This document defines a **production-grade Kubernetes policy governance framework** using **Kyverno**, aligned with the **CIS Kubernetes Benchmark**. It includes:

- Namespace-aware tier selection (baseline / restricted / hardened)
- CIS audit evidence pack structure
- Time-bound exception workflows with expiry
- Automated conversion strategy from existing OPA/Gatekeeper repositories
- GitOps, observability, and enforcement readiness

This document is designed for **download, audit submission, and platform handover**.

---

## 2. Policy Tier Model

| Tier | Purpose | Enforcement |
|----|----|----|
| baseline | Minimum CIS compliance | Enforce |
| restricted | Strong isolation | Enforce |
| hardened | Zero-trust + supply chain | Enforce + Verify |

Tiers are cumulative:
```
baseline ⊂ restricted ⊂ hardened
```

---

## 3. Namespace-Aware Tier Selection (Production)

### 3.1 Namespace Label Contract

Namespaces MUST declare a tier:

```yaml
metadata:
  labels:
    policy-tier: baseline | restricted | hardened
```

### 3.2 Tier Selector Pattern (Reusable)

```yaml
match:
  resources:
    namespaces:
    - "{{ request.namespace }}"
    selector:
      matchLabels:
        policy-tier: baseline
```

### 3.3 Example: Tier-Aware Privileged Container Policy

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: tier-baseline-disallow-privileged
spec:
  validationFailureAction: Enforce
  rules:
  - name: disallow-privileged
    match:
      resources:
        kinds: ["Pod"]
        selector:
          matchLabels:
            policy-tier: baseline
    validate:
      message: "Privileged containers are not allowed"
      pattern:
        spec:
          containers:
          - =(securityContext):
              =(privileged): false
```

This pattern is applied consistently across all tiers.

---

## 4. CIS Kubernetes Benchmark Mapping

| CIS Control | Enforcement |
|-----------|------------|
| 5.2.1 Privileged containers | validate |
| 5.2.5 Run as non-root | validate |
| 5.2.6 Read-only root FS | validate |
| 5.2.8 Image provenance | verifyImages |
| 5.3.1 Network segmentation | generate |
| 5.4.2 Resource limits | validate |

---

## 5. CIS Audit Evidence Pack (Production)

### 5.1 Evidence Categories

| Evidence Type | Source |
|-------------|-------|
| Policy definitions | Git repository |
| Enforcement proof | PolicyReports |
| Runtime compliance | Prometheus metrics |
| Drift detection | Argo CD sync history |
| Exceptions | Kyverno annotations |

### 5.2 Commands for Audit Evidence

```bash
kubectl get clusterpolicy -o yaml
kubectl get policyreport -A -o yaml
kubectl get clusterpolicyreport -o yaml
```

### 5.3 Audit Artifact Bundle

```
audit-pack/
├── policies/
├── policy-reports/
├── prometheus-snapshots/
├── argocd-sync-history/
└── exception-register.yaml
```

---

## 6. Exception Workflow with Expiry (Production)

### 6.1 Exception Design Principles

- Explicit opt-in
- Time-bound
- Auditable
- Auto-expiring

### 6.2 Exception Annotation Contract

```yaml
metadata:
  annotations:
    kyverno.io/ignore: "true"
    kyverno.io/ignore-until: "2026-06-30"
    kyverno.io/ignore-reason: "Legacy workload dependency"
```

### 6.3 Expiry Enforcement Policy

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: enforce-exception-expiry
spec:
  validationFailureAction: Enforce
  rules:
  - name: deny-expired-exception
    match:
      resources:
        kinds: ["Pod"]
    preconditions:
    - key: "{{ time_now_utc() }}"
      operator: GreaterThan
      value: "{{ request.object.metadata.annotations.kyverno.io/ignore-until }}"
    validate:
      message: "Policy exception has expired"
      deny: {}
```

---

## 7. Gatekeeper → Kyverno Conversion (Automated)

### 7.1 Supported Constraint Mapping

| Gatekeeper Constraint | Kyverno Equivalent |
|---------------------|-------------------|
| K8sPSPPrivilegedContainer | validate privileged=false |
| K8sRequiredResources | validate requests/limits |
| K8sPSPReadOnlyRootFilesystem | validate readOnlyRootFilesystem |
| K8sAllowedRepos | verifyImages |
| K8sBlockNodePort | validate Service type |

### 7.2 Automated Conversion Process

```
1. Parse ConstraintTemplate (Rego)
2. Identify constraint intent
3. Map to Kyverno rule type
4. Generate YAML policy
5. Assign policy tier
6. Commit to Git
```

### 7.3 Conversion Output Structure

```
converted-policies/
├── baseline/
├── restricted/
└── hardened/
```

---

## 8. GitOps Enforcement (Argo CD)

### 8.1 Repository Layout

```
platform-policies/
├── kyverno/
│   ├── baseline/
│   ├── restricted/
│   └── hardened/
└── kustomization.yaml
```

### 8.2 Sync Guarantees

- Automated sync
- Drift correction
- Immutable history

---

## 9. Observability & Alerting

### 9.1 Key Metrics

- kyverno_policy_results_total
- kyverno_admission_requests_total
- kyverno_background_scan_duration

### 9.2 Alert: Policy Violation

```yaml
alert: KyvernoPolicyViolation
expr: kyverno_policy_results_total{result="fail"} > 0
for: 5m
severity: critical
```

---

## 10. Operational Guardrails

**Mandatory**
- PR approval for policy changes
- Audit before enforce
- Tier labels required on namespaces

**Recommended**
- Separate platform vs app policies
- Quarterly CIS re-validation
- Export PolicyReports to SIEM

---

## 11. Executive Outcome

- CIS-aligned enforcement
- Namespace-aware zero trust
- Auditable exception handling
- Gatekeeper fully replaceable
- GitOps-native and observable

---

## 12. Multi-Cluster / Fleet Governance Extensions (Production)

### 12.1 Fleet Governance Objectives

Multi-cluster governance extends Kyverno from a **single-cluster control plane** to a **fleet-wide policy authority**.

Primary objectives:
- Consistent CIS enforcement across all clusters
- Centralized policy lifecycle management
- Cluster-specific overrides without drift
- Unified audit and evidence aggregation

---

### 12.2 Fleet Architecture Models

#### Model A: Central GitOps Control Plane (Recommended)

- One central Git repository for all policies
- One Argo CD control plane
- One Kyverno instance per cluster

```
Git (Policies)
   |
Argo CD (Hub)
   |--- Cluster A (Kyverno)
   |--- Cluster B (Kyverno)
   |--- Cluster C (Kyverno)
```

Benefits:
- Single source of truth
- Deterministic rollout
- Simplified audit trail

---

#### Model B: Hierarchical Policy Inheritance

```
fleet/
├── global/
│   ├── baseline/
│   ├── restricted/
│   └── hardened/
├── region-apac/
│   └── overrides/
├── region-eu/
│   └── overrides/
└── cluster-prod-01/
    └── exceptions/
```

Inheritance order:
```
Global → Region → Cluster
```

---

### 12.3 Cluster Identity Contract

Each cluster MUST expose identity labels:

```yaml
metadata:
  labels:
    fleet.cluster.name: prod-01
    fleet.cluster.env: production
    fleet.cluster.region: apac
```

These labels are consumed by Argo CD and Kyverno selectors.

---

### 12.4 Cluster-Aware Policy Targeting

Example: Apply hardened tier only to production clusters

```yaml
match:
  resources:
    kinds: ["Pod"]
    selector:
      matchLabels:
        fleet.cluster.env: production
```

---

### 12.5 Fleet-Level Exception Governance

#### Exception Scope

| Scope | Usage |
|----|----|
| Namespace | App-specific |
| Cluster | Legacy platform |
| Fleet | Emergency break-glass |

#### Fleet Exception Registry

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fleet-exception-registry
  namespace: kyverno
  labels:
    governance: fleet
```

All exceptions MUST reference a registry entry.

---

### 12.6 Fleet-Wide CIS Evidence Aggregation

#### Evidence Sources

- ClusterPolicyReports (per cluster)
- Prometheus metrics (per cluster)
- Argo CD sync status (global)

#### Aggregation Flow

```
Clusters → Prometheus Federation → Central Prometheus
Clusters → PolicyReports → Central Object Storage
Argo CD → Audit Log Store
```

Result: Single CIS evidence pack for the entire fleet.

---

### 12.7 Drift Detection and Enforcement

Controls:
- Argo CD drift detection
- Kyverno background scans
- Immutable Git history

Any deviation triggers:
- Alertmanager notification
- Automatic reconciliation
- Audit log entry

---

### 12.8 Multi-Cluster Promotion Pipeline

```
DEV → Audit
STAGE → Enforce (Canary)
PROD → Enforce (Fleet)
```

Promotion gates:
- Zero policy failures
- Audit evidence generated
- Security approval recorded

---

### 12.9 Executive Outcome (Fleet Mode)

- Uniform CIS compliance across clusters
- Centralized governance with local autonomy
- Scalable to 100+ clusters
- Single audit package per fleet

---

**End of Document**

