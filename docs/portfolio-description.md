# Portfolio page

## Project name

KubeMedic

## Short description

A Kubernetes reliability lab that detects workload failures, keeps the evidence, tracks recovery, and allows a Deployment change only after a person approves it.

## Problem

Kubernetes restarts containers and replaces Pods. That behavior does not explain the failure, show the evidence, or prove that a later edit actually took effect.

## Solution

KubeMedic watches TaskFlow on a local kind cluster. Rules classify the incident. The lifecycle is open, recovering, and resolved. Prometheus and Grafana show the metrics. A separate, narrow ServiceAccount can restart, roll back, or scale a Deployment after human approval. An optional AI pass can comment on sanitized evidence and cannot call the API server.

## Tech stack

React, TypeScript, FastAPI, PostgreSQL, Docker, Kubernetes, kind, Prometheus, Grafana, kube-state-metrics, cAdvisor, GitHub Actions, Trivy, gitleaks, kubeconform, CycloneDX, Terraform. OpenAI is an optional client and is disabled in this lab.

## Highlights

- Live investigations on kind, including a CrashLoopBackOff rollback that was verified only after the Deployment generation changed.
- Read-only watcher and a separate remediator. Remediation is off by default.
- CI that tests, scans, and publishes an SBOM, and does not deploy.
- An EKS, ECR, and GitHub OIDC design in Terraform. Not provisioned. AWS infrastructure cost: $0.

## Architecture summary

The user talks to TaskFlow. TaskFlow runs on kind. KubeMedic watches that namespace, writes an investigation, and, only with approval, patches a Deployment. Prometheus scrapes the applications, kube-state-metrics, and cAdvisor. Grafana reads Prometheus. GitHub Actions stops at build and scan. The AWS diagram is a reference beside the lab, not the runtime.

## GitHub CTA

Read the incident write-up for INV-000019, then the Terraform README that explains why nothing was applied.
