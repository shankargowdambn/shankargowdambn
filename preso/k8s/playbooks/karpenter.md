# Karpenter
Karpenter simplifies Kubernetes infrastructure with the right nodes at the right time. Karpenter automatically launches just the right compute resources.

Karpenter automatically launches just the right compute resources to handle your cluster's applications. It is designed to let you take full advantage of the cloud with fast and simple compute provisioning for Kubernetes clusters.
Karpenter improves the efficiency and cost of running workloads on Kubernetes clusters by:

- Watching for pods that the Kubernetes scheduler has marked as unschedulable
- Evaluating scheduling constraints (resource requests, nodeselectors, affinities, tolerations, and topology spread constraints) requested by the pods
- Provisioning nodes that meet the requirements of the pods
- Removing the nodes when the nodes are no longer needed
# Production-Ready Karpenter Configuration (Stateless, Stateful, and Specialized Workloads)

This document provides a **production-grade Karpenter setup** covering stateless services, stateful workloads, batch jobs, GPU/spot usage, and platform-level safeguards. It is designed for **AWS EKS**, but patterns translate to other providers with equivalent constructs.

---

## 1. Design Principles

- **Workload isolation by intent** (stateless, stateful, batch, system)
- **Predictable disruption control** for stateful systems
- **Cost efficiency** via Spot where safe
- **Security by default** (IMDSv2, least privilege, taints)
- **Operational safety** (budgets, TTLs, limits)

---

## 2. Global Prerequisites

- Kubernetes >= 1.27
- Karpenter >= v0.35+
- IAM Roles for Service Accounts (IRSA)
- VPC CNI with prefix delegation enabled

### Mandatory Tags on Subnets & Security Groups

```text
kubernetes.io/cluster/<cluster-name> = owned
karpenter.sh/discovery = <cluster-name>
```

---

## 3. Common EC2NodeClass (Baseline)

```yaml
apiVersion: karpenter.k8s.aws/v1beta1
kind: EC2NodeClass
metadata:
  name: baseline
spec:
  amiFamily: AL2
  role: KarpenterNodeRole-<cluster>
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: <cluster>
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: <cluster>
  metadataOptions:
    httpEndpoint: enabled
    httpTokens: required
  blockDeviceMappings:
    - deviceName: /dev/xvda
      ebs:
        volumeSize: 100Gi
        volumeType: gp3
        encrypted: true
  tags:
    Environment: prod
    ManagedBy: karpenter
```

---

## 4. Stateless Workloads (Web, APIs, Microservices)

### NodePool: Stateless On-Demand + Spot Mix

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: stateless
spec:
  disruption:
    consolidationPolicy: WhenUnderutilized
    expireAfter: 720h
  limits:
    cpu: "500"
  template:
    metadata:
      labels:
        workload-type: stateless
    spec:
      nodeClassRef:
        name: baseline
      taints:
        - key: stateless
          effect: NoSchedule
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand", "spot"]
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["m6i.large", "m6i.xlarge", "c6i.large"]
```

### Pod Spec Snippet

```yaml
nodeSelector:
  workload-type: stateless
tolerations:
  - key: stateless
    operator: Exists
```

---

## 5. Stateful Workloads (Databases, Kafka, Elasticsearch)

### Key Rules

- **NO spot instances**
- **NO aggressive consolidation**
- **Dedicated node pools**
- **Topology spread enforced**

### NodePool: Stateful

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: stateful
spec:
  disruption:
    consolidationPolicy: Never
    expireAfter: Never
  limits:
    cpu: "200"
  template:
    metadata:
      labels:
        workload-type: stateful
    spec:
      nodeClassRef:
        name: baseline
      taints:
        - key: stateful
          effect: NoSchedule
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["r6i.xlarge", "r6i.2xlarge"]
```

### Pod Hardening

```yaml
podAntiAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchLabels:
          app: kafka
      topologyKey: kubernetes.io/hostname
```

---

## 6. Batch / Jobs / CI Runners

### NodePool: Ephemeral Batch

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: batch
spec:
  disruption:
    consolidationPolicy: WhenEmpty
    expireAfter: 48h
  template:
    metadata:
      labels:
        workload-type: batch
    spec:
      nodeClassRef:
        name: baseline
      taints:
        - key: batch
          effect: NoSchedule
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot"]
```

---

## 7. GPU / ML / AI Workloads

```yaml
requirements:
  - key: node.kubernetes.io/instance-type
    operator: In
    values: ["g5.xlarge", "g4dn.xlarge"]
  - key: karpenter.sh/capacity-type
    operator: In
    values: ["on-demand"]
```

Add **nvidia.com/gpu** resource requests at pod level.

---

## 8. Platform / System Workloads

- CoreDNS
- Ingress Controllers
- Observability stack

### Rule

- Run on **on-demand only**
- Isolate from application churn

```yaml
labels:
  workload-type: system
```

---

## 9. Disruption Budgets (Critical)

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
spec:
  disruption:
    budgets:
      - nodes: "10%"
        reasons: ["Drifted", "Underutilized"]
```

---

## 10. Security & Compliance Checklist

- IMDSv2 enforced
- EBS encryption enabled
- No wildcard instance types in prod
- Separate NodePools per trust boundary
- Pod Security Standards: restricted

---

## 11. Observability & Operations

- Export Karpenter metrics to Prometheus
- Alert on:
  - Failed provisioning
  - Spot interruption rate
  - Node churn

---

## 12. Anti-Patterns (DO NOT DO)

- Mixing stateful and stateless workloads
- Using Spot for databases
- Single NodePool for all workloads
- Unlimited instance-type selectors

---

## 13. Reference Architecture Summary

| Workload | Capacity | Consolidation | TTL |
|--------|--------|--------------|-----|
| Stateless | Spot + OD | Aggressive | 30d |
| Stateful | OD only | Disabled | Never |
| Batch | Spot | WhenEmpty | 48h |
| System | OD only | Minimal | 90d |

---

## 14. Banking / FinTech Hardened Profile (PCI-DSS Aligned – OCI Focused)

This section defines a **PCI-DSS v4.0–aligned hardening profile for Karpenter on Oracle Cloud Infrastructure (OCI)**. While OCI-native constructs are referenced, the **patterns translate directly** to AWS, Azure, or GCP using equivalent primitives.

---

## 14.1 Regulatory Design Assumptions

- PCI-DSS v4.0 (Cardholder Data Environment – CDE)
- Zero-trust networking model
- Strict blast-radius isolation between workloads
- Immutable infrastructure and auditable change control

---

## 14.2 OCI-to-Cloud Construct Mapping

| Security Intent | OCI Construct | AWS / Azure / GCP Equivalent |
|---------------|--------------|------------------------------|
| Node identity | OCI Instance Principals | IRSA / Managed Identity / Workload Identity |
| Network isolation | OCI VCN + Security Lists | VPC + SG / VNet + NSG / VPC FW |
| Disk encryption | OCI Vault KMS | AWS KMS / Azure Key Vault / Cloud KMS |
| Image hardening | OCI Custom Images | AMI / Managed Image / Image Family |
| Audit logging | OCI Audit Service | CloudTrail / Azure Monitor / Audit Logs |

---

## 14.3 Mandatory Node Segmentation Model (PCI)

| NodePool | Purpose | Preemptible | Consolidation |
|--------|-------|------------|---------------|
| system | Core platform services | ❌ | Minimal |
| stateless-secure | APIs, UI, BFF | ❌ | Controlled |
| stateful-secure | Databases, MQ | ❌ | Disabled |
| batch-secure | Settlement, reconciliation | ❌ | WhenEmpty |
| dmz | Ingress, API Gateway | ❌ | Minimal |

**OCI Preemptible capacity is forbidden in PCI scopes.**

---

## 14.4 OCI NodeClass (PCI-Hardened Baseline)

```yaml
apiVersion: karpenter.k8s.aws/v1beta1
kind: EC2NodeClass # Conceptual equivalent for OCI
metadata:
  name: pci-baseline-oci
spec:
  imageFamily: Oracle-Linux-8
  instanceProfile: oci-instance-principal
  subnetSelectorTerms:
    - tags:
        pci-zone: "true"
  securityGroupSelectorTerms:
    - tags:
        pci-zone: "true"
  metadataOptions:
    httpEndpoint: enabled
    httpTokens: required
  blockDeviceMappings:
    - deviceName: /dev/sda
      ebs:
        volumeSize: 200Gi
        volumeType: balanced
        encrypted: true
        kmsKeyID: ocid1.key.oc1..<pci-key>
  tags:
    Compliance: pci
    DataClass: regulated
    Cloud: oci
```

> **Note:** Replace EC2NodeClass with the OCI-specific NodeClass CRD once enabled; controls remain identical.

---

## 14.5 Stateless Secure NodePool (OCI)

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: stateless-secure
spec:
  disruption:
    consolidationPolicy: WhenUnderutilized
    expireAfter: 2160h
  template:
    metadata:
      labels:
        workload-type: stateless-secure
        pci-scope: in
    spec:
      nodeClassRef:
        name: pci-baseline-oci
      taints:
        - key: pci
          effect: NoSchedule
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["VM.Standard.E4.Flex"]
```

---

## 14.6 Stateful Secure NodePool (OCI)

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: stateful-secure
spec:
  disruption:
    consolidationPolicy: Never
    expireAfter: Never
  template:
    metadata:
      labels:
        workload-type: stateful-secure
        pci-scope: in
    spec:
      nodeClassRef:
        name: pci-baseline-oci
      taints:
        - key: pci-stateful
          effect: NoSchedule
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["VM.Standard.E4.Flex"]
```

---

## 14.7 Pod-Level Mandatory PCI Controls

```yaml
securityContext:
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
```

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "1Gi"
```

---

## 14.8 Network Isolation (OCI)

- Dedicated OCI VCN for CDE
- Security Lists + NSGs deny-by-default
- Kubernetes NetworkPolicies for east–west traffic
- Egress restricted to:
  - Payment processors
  - Tokenization services
  - Central logging endpoints

---

## 14.9 Change & Disruption Control

```yaml
budgets:
  - nodes: "5%"
    reasons: ["Drifted"]
```

- No automated image rotation during settlement windows
- Manual approval for NodeClass drift remediation

---

## 14.10 Observability & Audit (OCI)

- OCI Audit Service enabled
- Kubernetes audit logs shipped to OCI Object Storage (immutable)
- Node lifecycle events retained for ≥ 1 year

---

## 14.11 Mandatory Policy Enforcement

**Kyverno / OPA (OCI-neutral rules):**

- Deny preemptible capacity in pci-scope
- Enforce nodeSelector + tolerations
- Enforce non-root containers
- Require resource requests and limits

---

## 14.12 Explicit PCI Anti-Patterns

- Preemptible / Spot nodes in CDE
- Mixed-trust NodePools
- Automatic consolidation for databases
- Public subnets for PCI workloads
- Unencrypted boot volumes

---

## 14.13 PCI Reference Architecture Summary

| Layer | OCI Control |
|------|------------|
| Compute | On-demand only NodePools |
| Storage | OCI Block Volume + Vault KMS |
| Network | Isolated VCN + NSGs |
| Identity | Instance Principals |
| Ops | Controlled disruption + audit logs |

---

## Karpenter Implementations

Karpenter is a multi-cloud project with implementations by the following cloud providers:

- [Multi-cloud project](https://github.com/kubernetes-sigs/karpenter)
- Oracle Cloud Infrastructure (OCI)

### Oracle Cloud Infrastructure (OCI) Preparation
- create a compartment, karpenter-oci will launch instance in this compartment
- create an OKE cluster in the created compartment
- create policy in oracle console for the Karpenter service account, the name could like karpenter-oke-policy, the statements as below:
- any-user can be oke-dyn-grp for dynamic group usage
```yaml
Allow any-user to manage instance-family in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to manage instances in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to read instance-images in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to read app-catalog-listing in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to manage volume-family in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to manage volume-attachments in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to use volumes in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to use virtual-network-family in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to inspect vcns in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to use subnets in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to use network-security-groups in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to use vnics in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
Allow any-user to use tag-namespaces in tenancy where all {request.principal.type = 'workload',request.principal.namespace = 'karpenter',request.principal.service_account = 'karpenter'}
```

- create a dynamic group and policy in the oracle console to support Self-Managed Nodes
```yaml
Allow dynamic-group <dynamic-group-name> to {CLUSTER_JOIN} in compartment <compartment-name>
```
- create tag namespace inside the created compartment, the namespace name could like oke-karpenter-ns, the required keys show in below sheet, if you want to attach more customer tags, you also can add them in the namespace.

| key                               | description                                   |
|:----------------------------------|:----------------------------------------------|
| karpenter_k8s_oracle/ocinodeclass | the name of nodeclass used to crate instance  |
| karpenter_sh/managed-by           | the OKE cluster name                          |
| karpenter_sh/nodepool             | the name of nodepool used to create instance  |
| karpenter_sh/nodeclaim            | the name of nodeclaim used to create instance |


### Install
replace the clusterName, clusterEndpoint, clusterDns, compartmentId, ociResourcePrincipalRegion with yours.
```
kubectl apply -f ./pkg/apis/crds/
helm upgrade --install karpenter ./charts/karpenter --namespace "karpenter" --create-namespace --set "settings.clusterName=karpenter-oci-test" --set "settings.clusterEndpoint=https://10.0.0.8:6443" --set "settings.clusterDns=10.96.5.5" --set "settings.compartmentId=ocid1.compartment.oc1..aaaaaaaa" --set "settings.ociResourcePrincipalRegion=us-ashburn-1"
```

#### or you can install from helm git repo 
```
helm repo add karpenter-oci https://zoom.github.io/karpenter-oci
```
If you had already added this repo earlier, run `helm repo update` to retrieve the latest versions of the packages.
You can then run `helm search repo karpenter-oci` to see the charts.

To install the karpenter chart, also replace the clusterName, clusterEndpoint, clusterDns, compartmentId, ociResourcePrincipalRegion with yours:
```
helm install karpenter karpenter-oci/karpenter --version 1.4.1 --namespace "karpenter" --create-namespace --set "settings.clusterName=karpenter-oci-test" --set "settings.clusterEndpoint=https://10.0.0.8:6443" --set "settings.clusterDns=10.96.5.5" --set "settings.compartmentId=ocid1.compartment.oc1..aaaaaaaa" --set "settings.ociResourcePrincipalRegion=us-ashburn-1"
```
To uninstall the chart:
```
helm uninstall karpenter
```
setting details

| setting                    | description                                                                                                                                | default                      |
|----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|------------------------------|
| clusterName                | cluster name                                                                                                                               |                              |
| clusterEndpoint            | api server private endpoint                                                                                                                |                              |
| clusterDns                 | IP addresses for the cluster DNS server, general is core dns ip                                                                            |                              |
| compartmentId              | the compartment id or your worker nodes                                                                                                    |                              |
| ociResourcePrincipalRegion | the region your cluster belong to, refer [issue](https://github.com/oracle/oci-go-sdk/issues/489)                                          |                              |
| ociAuthMethods             | API_KEY, OKE, SESSION, INSTANCE_PRINCIPAL                                                                                                  | OKE                          |
| flexCpuConstrainList       | to constrain the ocpu cores of flex instance, instance create in this cpu size list, ocpu is twice of vcpu                                 | "1,2,4,8,16,32,48,64,96,128" |
| flexCpuMemRatios           | the ratios of vcpu and mem, eg. FLEX_CPU_MEM_RATIOS=2,4, if create flex instance with 2 cores(1 ocpu), mem should be 4Gi or 8Gi            | "2,4,8"                      |
| tagNamespace               | The tag namespace used to create and list instances by karpenter-oci, karpenter-oci will attach nodepool and nodeclass tag on the instance | oke-karpenter-ns             |
| vmMemoryOverheadPercent    | he VM memory overhead as a percent that will be subtracted from the total memory for all instance types                                    | 0.075                        |

