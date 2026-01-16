# Tracing Network Latency in OCI Multi-Cluster (SRE Playbook)
## Problem Statement (SRE View)

“We see elevated p99 latency between services across clusters or regions in OCI. Where exactly is the delay introduced?”

Network latency in OCI can originate from six distinct layers:

1. Application

2. Kubernetes

3. Node / Kernel

4. Cluster Networking

5. OCI Networking

6. Inter-Region / External Dependency

Your job as SRE is to prove which layer is responsible, with evidence

```textmate
User Latency
 → Service-to-Service Latency
   → Pod-to-Pod
     → Node-to-Node
       → VCN / Subnet
         → DRG / LPG / FastConnect
           → Region / External Service
```
## Tooling Stack (What You MUST Have)
### Mandatory (Production)
| Layer        | Tools                               |
|--------------|-------------------------------------|
| App → Kernel | Coroot (eBPF)                       |
| Metrics      | Prometheus / VictoriaMetrics        |
| Logs         | Loki / OpenSearch                   |
| OCI Infra    | OCI Monitoring                      |
| Packet       | tcpdump (controlled), eBPF          |
| Routing      | OCI VCN Flow Logs                   |
| mtr          | tcptraceroute                       |
| WIndows      | iperf3 (maintenance windows only)   |
| Kubernetes   | Cilium Hubble (if using Cilium CNI) |

# OCI Network Debugging Runbook  

## From Public Domain → Load Balancer → Backend → Pod → Kernel

**Audience:** SRE / Platform / Cloud Networking  
**Environment:** Oracle Cloud Infrastructure (OCI), OKE, Multi-Cluster  
**Use Case:** Latency, timeout, packet loss, intermittent failures

---

## 0. Entry Point – Public Domain / Public IP

Users report latency, timeouts, or failures hitting `api.example.com`.

### Tools
- dig
- nslookup
- curl
- mtr

### Validation
```bash
dig api.example.com +short
```

---

## 1. OCI Public Load Balancer (LBaaS)

### 1.1 Listener Validation
- Protocol, ports
- Idle timeout
- TLS version and cipher

### 1.2 Backend Set
- Policy (Round Robin / IP Hash)
- Health check protocol and port
- Health check timeout and interval

---

## 2. IAM Policies (Mandatory Visibility)

```text
Allow group sre-team to read virtual-network-family
Allow group sre-team to read load-balancers
Allow group sre-team to read metrics
Allow group sre-team to read log-groups
```

---

## 3. Security Lists & NSGs

### Security Lists
- LB subnet ingress
- Node subnet ingress/egress
- Ephemeral ports (1024–65535)

### NSGs
- LB NSG → Node NSG
- Node NSG → Pod CIDR

---

## 4. Route Tables

Expected path:
```text
Internet → LB Subnet → Node Subnet → Pod CIDR
```

Check for:
- NAT Gateway in path
- Wrong DRG or LPG routes
- Asymmetric routing

---

## 5. OCI Flow Logs (Authoritative)

Patterns:
- ACCEPT at LB, DROP at node → security issue
- ACCEPT with high RTT → routing issue
- No logs → route miss

---

## 6. Kubernetes Ingress

Metrics:
- request_duration
- upstream_response_time
- connect_time
- tls_handshake_time

---

## 7. Kubernetes Services & Endpoints

- Endpoint fan-out
- Endpoint churn
- kube-proxy mode (iptables vs IPVS)

---

## 8. Pod-Level Network Tracing (eBPF)

Metrics:
- TCP RTT
- Retransmits
- Socket queue depth

---

## 9. Node & Kernel Layer

- SoftIRQ saturation
- NIC drops
- MTU mismatch

---

## 10. Cross-Cluster / Region Baselines

| Path         | RTT     |
|--------------|---------|
| Same AZ      | <1ms    |
| Same region  | 1–3ms   |
| Cross region | 10–40ms |

---

## 11. End-to-End Proof Chain

```text
DNS → LB → Backend → Flow Logs → Ingress → Pod → Node
```

---

## 12. Common OCI Root Causes

1. Missing ephemeral ports
2. NAT gateway in data path
3. MTU mismatch
4. Backend health check mismatch
5. Route table regression
6. Asymmetric DRG routing

---

## Final Rule

If you cannot trace a packet end-to-end with logs and metrics, the RCA is incomplete.
