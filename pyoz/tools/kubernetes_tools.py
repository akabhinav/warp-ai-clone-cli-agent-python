"""Kubernetes tools — deploy, manage, and monitor workloads on Kubernetes clusters.

Full enterprise-grade Kubernetes lifecycle: cluster management, deployments,
services, pods, configmaps, secrets, namespaces, logs, scaling, rollouts,
Helm charts, and manifest application.
Cross-platform: works wherever kubectl/helm CLI is installed.
"""

import os
import shutil
import subprocess
from typing import Any

COMMAND_TIMEOUT = 300  # K8s operations can be slow


def _run(args: list[str], cwd: str | None = None, timeout: int = COMMAND_TIMEOUT) -> dict[str, Any]:
    """Run a command and return result dict."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "exit_code": result.returncode}
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"Command not found: {args[0]}", "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timed out after {timeout}s", "exit_code": -1}


def _fmt(r: dict[str, Any]) -> str:
    parts = []
    if r["stdout"]:
        parts.append(r["stdout"])
    if r["stderr"] and r["exit_code"] != 0:
        parts.append(f"STDERR: {r['stderr']}")
    elif r["stderr"] and r["exit_code"] == 0:
        # kubectl often writes status to stderr
        parts.append(r["stderr"])
    if r["exit_code"] != 0 and not parts:
        parts.append(f"Exit code: {r['exit_code']}")
    return "\n".join(parts) if parts else "Done."


def _ns_args(namespace: str) -> list[str]:
    """Build namespace flags."""
    if namespace == "all":
        return ["--all-namespaces"]
    elif namespace:
        return ["-n", namespace]
    return []


def kubernetes_tool(
    action: str,
    target: str = "",
    namespace: str = "",
    args: str = "",
    cwd: str | None = None,
) -> str:
    """Kubernetes cluster and workload management.

    Args:
        action: One of:
          Cluster: cluster-info, get-contexts, use-context, get-nodes, top-nodes
          Namespaces: get-namespaces, create-namespace, delete-namespace
          Workloads: get-pods, get-deployments, get-services, get-statefulsets,
                     get-daemonsets, get-jobs, get-cronjobs, get-ingresses
          Deploy: apply, delete, create-deployment, scale, set-image,
                  rollout-status, rollout-history, rollout-undo, rollout-restart
          Pod Ops: logs, exec, describe, port-forward, get-events
          Config: get-configmaps, get-secrets, create-configmap, create-secret
          Helm: helm-install, helm-upgrade, helm-uninstall, helm-list,
                helm-repo-add, helm-repo-update, helm-search, helm-status
          Advanced: kustomize, top-pods, get-all, get-pvc, get-hpa, cordon,
                    uncordon, drain, taint, label, annotate
        target: Resource name, file path, or Helm release name
        namespace: Kubernetes namespace (default: current context namespace, "all" for all)
        args: Additional flags (e.g. "--replicas=3", "-l app=web", "-f values.yaml")
        cwd: Working directory
    """
    if not shutil.which("kubectl"):
        return "Error: kubectl not found. Install from https://kubernetes.io/docs/tasks/tools/"

    action = action.lower().strip()
    work_dir = cwd or os.getcwd()
    extra = args.split() if args else []
    ns = _ns_args(namespace)

    # ── Cluster Info ──────────────────────────────────────────

    if action == "cluster-info":
        return _fmt(_run(["kubectl", "cluster-info"], work_dir))

    elif action == "get-contexts":
        return _fmt(_run(["kubectl", "config", "get-contexts"], work_dir))

    elif action == "use-context":
        if not target:
            return "Error: 'target' (context name) required"
        return _fmt(_run(["kubectl", "config", "use-context", target], work_dir))

    elif action == "get-nodes":
        cmd = ["kubectl", "get", "nodes", "-o", "wide"] + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "top-nodes":
        return _fmt(_run(["kubectl", "top", "nodes"] + extra, work_dir))

    # ── Namespaces ────────────────────────────────────────────

    elif action == "get-namespaces":
        return _fmt(_run(["kubectl", "get", "namespaces"] + extra, work_dir))

    elif action == "create-namespace":
        if not target:
            return "Error: 'target' (namespace name) required"
        return _fmt(_run(["kubectl", "create", "namespace", target], work_dir))

    elif action == "delete-namespace":
        if not target:
            return "Error: 'target' (namespace name) required"
        return _fmt(_run(["kubectl", "delete", "namespace", target], work_dir))

    # ── Get Resources ─────────────────────────────────────────

    elif action in (
        "get-pods", "get-deployments", "get-services", "get-statefulsets",
        "get-daemonsets", "get-jobs", "get-cronjobs", "get-ingresses",
        "get-configmaps", "get-secrets", "get-pvc", "get-hpa",
    ):
        resource = action.replace("get-", "")
        cmd = ["kubectl", "get", resource, "-o", "wide"] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "get-all":
        cmd = ["kubectl", "get", "all", "-o", "wide"] + ns + extra
        return _fmt(_run(cmd, work_dir))

    # ── Deploy & Manage ───────────────────────────────────────

    elif action == "apply":
        if not target:
            return "Error: 'target' (manifest file or directory) required"
        path = target if os.path.isabs(target) else os.path.join(work_dir, target)
        if os.path.isdir(path):
            cmd = ["kubectl", "apply", "-f", path, "--recursive"] + ns + extra
        else:
            cmd = ["kubectl", "apply", "-f", path] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "delete":
        if not target:
            return "Error: 'target' (resource or manifest file) required"
        # Check if target is a file
        path = target if os.path.isabs(target) else os.path.join(work_dir, target)
        if os.path.exists(path):
            cmd = ["kubectl", "delete", "-f", path] + ns + extra
        else:
            # Treat as resource type/name like "deployment/myapp"
            cmd = ["kubectl", "delete", target] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "create-deployment":
        if not target:
            return "Error: 'target' (deployment name) required"
        if not args:
            return "Error: 'args' must include '--image=<image>' at minimum"
        cmd = ["kubectl", "create", "deployment", target] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "scale":
        if not target:
            return "Error: 'target' (deployment name) required"
        cmd = ["kubectl", "scale", f"deployment/{target}"] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "set-image":
        if not target or not args:
            return "Error: 'target' (deployment) and 'args' (container=image) required"
        cmd = ["kubectl", "set", "image", f"deployment/{target}"] + ns + extra
        return _fmt(_run(cmd, work_dir))

    # ── Rollouts ──────────────────────────────────────────────

    elif action == "rollout-status":
        if not target:
            return "Error: 'target' (deployment name) required"
        cmd = ["kubectl", "rollout", "status", f"deployment/{target}"] + ns + extra
        return _fmt(_run(cmd, work_dir, timeout=120))

    elif action == "rollout-history":
        if not target:
            return "Error: 'target' (deployment name) required"
        cmd = ["kubectl", "rollout", "history", f"deployment/{target}"] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "rollout-undo":
        if not target:
            return "Error: 'target' (deployment name) required"
        cmd = ["kubectl", "rollout", "undo", f"deployment/{target}"] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "rollout-restart":
        if not target:
            return "Error: 'target' (deployment name) required"
        cmd = ["kubectl", "rollout", "restart", f"deployment/{target}"] + ns + extra
        return _fmt(_run(cmd, work_dir))

    # ── Pod Operations ────────────────────────────────────────

    elif action == "logs":
        if not target:
            return "Error: 'target' (pod name) required"
        cmd = ["kubectl", "logs", "--tail=200"] + ns + extra + [target]
        return _fmt(_run(cmd, work_dir))

    elif action == "exec":
        if not target:
            return "Error: 'target' (pod name) required"
        if not args:
            return "Error: 'args' (command to run) required"
        cmd = ["kubectl", "exec", target] + ns + ["--"] + extra
        return _fmt(_run(cmd, work_dir, timeout=120))

    elif action == "describe":
        if not target:
            return "Error: 'target' (resource type/name, e.g. pod/mypod) required"
        cmd = ["kubectl", "describe", target] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "port-forward":
        if not target or not args:
            return "Error: 'target' (pod or svc/name) and 'args' (localPort:remotePort) required"
        return "Error: port-forward requires an interactive session. Use run_command instead with '&' to background it."

    elif action == "get-events":
        cmd = ["kubectl", "get", "events", "--sort-by=.metadata.creationTimestamp"] + ns + extra
        return _fmt(_run(cmd, work_dir))

    # ── ConfigMaps & Secrets ──────────────────────────────────

    elif action == "create-configmap":
        if not target:
            return "Error: 'target' (configmap name) required"
        if not args:
            return "Error: 'args' required (e.g. '--from-literal=key=value' or '--from-file=config.yaml')"
        cmd = ["kubectl", "create", "configmap", target] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "create-secret":
        if not target:
            return "Error: 'target' (secret name) required"
        if not args:
            return "Error: 'args' required (e.g. '--from-literal=password=pass123' or '--from-file=tls.crt')"
        cmd = ["kubectl", "create", "secret", "generic", target] + ns + extra
        return _fmt(_run(cmd, work_dir))

    # ── Helm ──────────────────────────────────────────────────

    elif action == "helm-install":
        if not shutil.which("helm"):
            return "Error: Helm not found. Install from https://helm.sh/docs/intro/install/"
        if not target or not args:
            return "Error: 'target' (release name) and 'args' (chart name or path) required"
        cmd = ["helm", "install", target] + ns + extra
        return _fmt(_run(cmd, work_dir, timeout=600))

    elif action == "helm-upgrade":
        if not shutil.which("helm"):
            return "Error: Helm not found."
        if not target or not args:
            return "Error: 'target' (release name) and 'args' (chart name or path) required"
        cmd = ["helm", "upgrade", target] + ns + extra
        return _fmt(_run(cmd, work_dir, timeout=600))

    elif action == "helm-uninstall":
        if not shutil.which("helm"):
            return "Error: Helm not found."
        if not target:
            return "Error: 'target' (release name) required"
        cmd = ["helm", "uninstall", target] + ns
        return _fmt(_run(cmd, work_dir))

    elif action == "helm-list":
        if not shutil.which("helm"):
            return "Error: Helm not found."
        cmd = ["helm", "list"] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "helm-repo-add":
        if not shutil.which("helm"):
            return "Error: Helm not found."
        if not target or not args:
            return "Error: 'target' (repo name) and 'args' (repo URL) required"
        cmd = ["helm", "repo", "add", target] + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "helm-repo-update":
        if not shutil.which("helm"):
            return "Error: Helm not found."
        return _fmt(_run(["helm", "repo", "update"], work_dir))

    elif action == "helm-search":
        if not shutil.which("helm"):
            return "Error: Helm not found."
        if not target:
            return "Error: 'target' (search keyword) required"
        cmd = ["helm", "search", "repo", target] + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "helm-status":
        if not shutil.which("helm"):
            return "Error: Helm not found."
        if not target:
            return "Error: 'target' (release name) required"
        cmd = ["helm", "status", target] + ns
        return _fmt(_run(cmd, work_dir))

    # ── Kustomize ─────────────────────────────────────────────

    elif action == "kustomize":
        path = target if target else "."
        if not os.path.isabs(path):
            path = os.path.join(work_dir, path)
        if "--apply" in extra or "-apply" in extra:
            extra_clean = [x for x in extra if x not in ("--apply", "-apply")]
            cmd = ["kubectl", "apply", "-k", path] + ns + extra_clean
        else:
            cmd = ["kubectl", "kustomize", path] + extra
        return _fmt(_run(cmd, work_dir))

    # ── Resource Metrics ──────────────────────────────────────

    elif action == "top-pods":
        cmd = ["kubectl", "top", "pods"] + ns + extra
        return _fmt(_run(cmd, work_dir))

    # ── Node Management ───────────────────────────────────────

    elif action == "cordon":
        if not target:
            return "Error: 'target' (node name) required"
        return _fmt(_run(["kubectl", "cordon", target], work_dir))

    elif action == "uncordon":
        if not target:
            return "Error: 'target' (node name) required"
        return _fmt(_run(["kubectl", "uncordon", target], work_dir))

    elif action == "drain":
        if not target:
            return "Error: 'target' (node name) required"
        cmd = ["kubectl", "drain", target, "--ignore-daemonsets", "--delete-emptydir-data"] + extra
        return _fmt(_run(cmd, work_dir, timeout=600))

    # ── Labels, Taints, Annotations ──────────────────────────

    elif action == "label":
        if not target or not args:
            return "Error: 'target' (resource type/name) and 'args' (key=value) required"
        cmd = ["kubectl", "label", target] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "annotate":
        if not target or not args:
            return "Error: 'target' (resource type/name) and 'args' (key=value) required"
        cmd = ["kubectl", "annotate", target] + ns + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "taint":
        if not target or not args:
            return "Error: 'target' (node name) and 'args' (key=value:effect) required"
        cmd = ["kubectl", "taint", "nodes", target] + extra
        return _fmt(_run(cmd, work_dir))

    else:
        return (
            "Error: Unknown action. Available actions:\n"
            "  Cluster:    cluster-info, get-contexts, use-context, get-nodes, top-nodes\n"
            "  Namespaces: get-namespaces, create-namespace, delete-namespace\n"
            "  Workloads:  get-pods, get-deployments, get-services, get-statefulsets,\n"
            "              get-daemonsets, get-jobs, get-cronjobs, get-ingresses\n"
            "  Deploy:     apply, delete, create-deployment, scale, set-image,\n"
            "              rollout-status, rollout-history, rollout-undo, rollout-restart\n"
            "  Pod Ops:    logs, exec, describe, port-forward, get-events\n"
            "  Config:     get-configmaps, get-secrets, create-configmap, create-secret\n"
            "  Helm:       helm-install, helm-upgrade, helm-uninstall, helm-list,\n"
            "              helm-repo-add, helm-repo-update, helm-search, helm-status\n"
            "  Advanced:   kustomize, top-pods, get-all, get-pvc, get-hpa,\n"
            "              cordon, uncordon, drain, taint, label, annotate"
        )
