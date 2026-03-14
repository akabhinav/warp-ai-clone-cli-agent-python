"""Environment Discovery — scans the system for installed databases, frameworks,
runtimes, and tools. Returns a structured inventory so the agent can make
informed stack decisions instead of guessing.

Cross-platform: Linux, macOS, Windows.
No external dependencies — uses subprocess, shutil.which, and os only.
"""

import json
import os
import platform
import shutil
import subprocess
from typing import Any

from pyoz.platform import IS_WINDOWS, IS_MACOS, IS_LINUX


def _run(args: list[str], timeout: int = 10) -> str:
    """Run a command quietly, return stdout (or stderr for java-style tools)."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (r.stdout.strip() or r.stderr.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return ""


def _which(name: str) -> str | None:
    """Check if a binary is on PATH."""
    return shutil.which(name)


def _version(cmd: list[str]) -> str:
    """Get first line of version output."""
    out = _run(cmd)
    return out.splitlines()[0].strip() if out else ""


def _is_sandbox() -> bool:
    """Check if running inside the PyOz Docker sandbox."""
    return os.environ.get("PYOZ_SANDBOX") == "1"


def _tcp_check(host: str, port: int, timeout: int = 3) -> bool:
    """Check if a TCP port is reachable (works inside Docker networks)."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError, TimeoutError):
        return False


def _detect_sandbox_services() -> dict[str, Any]:
    """Detect services available in the Docker sandbox via env vars and TCP checks."""
    services: dict[str, Any] = {}

    # PostgreSQL
    pg_host = os.environ.get("POSTGRES_HOST", "")
    if pg_host:
        port = int(os.environ.get("POSTGRES_PORT", 5432))
        services["postgres"] = {
            "name": "PostgreSQL",
            "engine_key": "postgres",
            "host": pg_host,
            "port": port,
            "user": os.environ.get("POSTGRES_USER", "pyoz"),
            "password": os.environ.get("POSTGRES_PASSWORD", ""),
            "database": os.environ.get("POSTGRES_DB", "app_db"),
            "connection_string": os.environ.get("DATABASE_URL", ""),
            "running": _tcp_check(pg_host, port),
        }

    # MySQL
    mysql_host = os.environ.get("MYSQL_HOST", "")
    if mysql_host:
        port = int(os.environ.get("MYSQL_PORT", 3306))
        services["mysql"] = {
            "name": "MySQL",
            "engine_key": "mysql",
            "host": mysql_host,
            "port": port,
            "user": os.environ.get("MYSQL_USER", "pyoz"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ.get("MYSQL_DATABASE", "app_db"),
            "running": _tcp_check(mysql_host, port),
        }

    # MongoDB
    mongo_host = os.environ.get("MONGO_HOST", "")
    if mongo_host:
        port = int(os.environ.get("MONGO_PORT", 27017))
        services["mongodb"] = {
            "name": "MongoDB",
            "engine_key": "mongodb",
            "host": mongo_host,
            "port": port,
            "user": os.environ.get("MONGO_USER", "pyoz"),
            "password": os.environ.get("MONGO_PASSWORD", ""),
            "database": os.environ.get("MONGO_DB", "app_db"),
            "connection_string": os.environ.get("MONGO_URL", ""),
            "running": _tcp_check(mongo_host, port),
        }

    # Redis
    redis_host = os.environ.get("REDIS_HOST", "")
    if redis_host:
        port = int(os.environ.get("REDIS_PORT", 6379))
        services["redis"] = {
            "name": "Redis",
            "engine_key": "redis",
            "host": redis_host,
            "port": port,
            "password": os.environ.get("REDIS_PASSWORD", ""),
            "connection_string": os.environ.get("REDIS_URL", ""),
            "running": _tcp_check(redis_host, port),
        }

    # Kafka
    kafka_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
    if kafka_servers:
        host_port = kafka_servers.split(",")[0]
        parts = host_port.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 9092
        services["kafka"] = {
            "name": "Apache Kafka",
            "host": host,
            "port": port,
            "bootstrap_servers": kafka_servers,
            "running": _tcp_check(host, port),
        }

    # RabbitMQ
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "")
    if rabbitmq_host:
        port = int(os.environ.get("RABBITMQ_PORT", 5672))
        services["rabbitmq"] = {
            "name": "RabbitMQ",
            "host": rabbitmq_host,
            "port": port,
            "user": os.environ.get("RABBITMQ_USER", "pyoz"),
            "password": os.environ.get("RABBITMQ_PASSWORD", ""),
            "connection_string": os.environ.get("RABBITMQ_URL", ""),
            "running": _tcp_check(rabbitmq_host, port),
        }

    # Elasticsearch
    es_host = os.environ.get("ELASTICSEARCH_HOST", "")
    if es_host:
        port = int(os.environ.get("ELASTICSEARCH_PORT", 9200))
        services["elasticsearch"] = {
            "name": "Elasticsearch",
            "host": es_host,
            "port": port,
            "url": os.environ.get("ELASTICSEARCH_URL", ""),
            "running": _tcp_check(es_host, port),
        }

    # MinIO
    minio_endpoint = os.environ.get("MINIO_ENDPOINT", "")
    if minio_endpoint:
        parts = minio_endpoint.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 9000
        services["minio"] = {
            "name": "MinIO (S3-compatible)",
            "host": host,
            "port": port,
            "access_key": os.environ.get("MINIO_ACCESS_KEY", ""),
            "secret_key": os.environ.get("MINIO_SECRET_KEY", ""),
            "running": _tcp_check(host, port),
        }

    return services


# ── Detection functions ──────────────────────────────────────

def _detect_databases() -> list[dict[str, Any]]:
    """Detect all installed/running database engines."""
    dbs: list[dict[str, Any]] = []

    checks = [
        {
            "name": "PostgreSQL",
            "binaries": ["psql", "pg_isready"],
            "version_cmd": ["psql", "--version"],
            "default_port": 5432,
            "engine_key": "postgres",
            "check_running": ["pg_isready", "-q"],
        },
        {
            "name": "MySQL",
            "binaries": ["mysql", "mysqld"],
            "version_cmd": ["mysql", "--version"],
            "default_port": 3306,
            "engine_key": "mysql",
            "check_running": ["mysqladmin", "ping", "--silent"],
        },
        {
            "name": "MariaDB",
            "binaries": ["mariadb"],
            "version_cmd": ["mariadb", "--version"],
            "default_port": 3306,
            "engine_key": "mysql",
            "check_running": ["mariadb-admin", "ping", "--silent"],
        },
        {
            "name": "SQLite",
            "binaries": ["sqlite3"],
            "version_cmd": ["sqlite3", "--version"],
            "default_port": None,
            "engine_key": "sqlite",
            "check_running": None,  # file-based, always available
        },
        {
            "name": "MongoDB",
            "binaries": ["mongod", "mongosh", "mongo"],
            "version_cmd": ["mongod", "--version"],
            "default_port": 27017,
            "engine_key": "mongodb",
            "check_running": ["mongosh", "--eval", "db.runCommand({ping:1})", "--quiet"],
        },
        {
            "name": "Redis",
            "binaries": ["redis-server", "redis-cli"],
            "version_cmd": ["redis-server", "--version"],
            "default_port": 6379,
            "engine_key": "redis",
            "check_running": ["redis-cli", "ping"],
        },
        {
            "name": "Microsoft SQL Server",
            "binaries": ["sqlcmd"],
            "version_cmd": ["sqlcmd", "-?"],
            "default_port": 1433,
            "engine_key": "mssql",
            "check_running": None,
        },
        {
            "name": "Elasticsearch",
            "binaries": ["elasticsearch"],
            "version_cmd": ["elasticsearch", "--version"],
            "default_port": 9200,
            "engine_key": "elasticsearch",
            "check_running": None,
        },
        {
            "name": "Cassandra",
            "binaries": ["cqlsh", "cassandra"],
            "version_cmd": ["cqlsh", "--version"],
            "default_port": 9042,
            "engine_key": "cassandra",
            "check_running": None,
        },
    ]

    for db in checks:
        installed_bins = [b for b in db["binaries"] if _which(b)]
        if not installed_bins:
            continue

        version = _version(db["version_cmd"]) if db["version_cmd"] else "unknown"

        running = False
        if db["check_running"]:
            result = _run(db["check_running"])
            running = bool(result) or "PONG" in (result or "").upper()
        elif db["engine_key"] == "sqlite":
            running = True  # always available

        dbs.append({
            "name": db["name"],
            "engine_key": db["engine_key"],
            "version": version,
            "installed": True,
            "running": running,
            "default_port": db["default_port"],
            "binaries": installed_bins,
        })

    return dbs


def _detect_web_frameworks() -> list[dict[str, Any]]:
    """Detect installed web framework CLIs and runtimes."""
    frameworks: list[dict[str, Any]] = []

    checks = [
        ("Django", ["django-admin", "--version"], "python", "pip install django"),
        ("Flask", ["flask", "--version"], "python", "pip install flask"),
        ("FastAPI", ["python3", "-c", "import fastapi; print(fastapi.__version__)"], "python", "pip install fastapi uvicorn"),
        ("Express.js", ["node", "-e", "console.log(require('express/package.json').version)"], "node", "npm install express"),
        ("Next.js", ["npx", "next", "--version"], "node", "npx create-next-app"),
        ("Rails", ["rails", "--version"], "ruby", "gem install rails"),
        ("Spring Boot", ["spring", "--version"], "java", "sdk install springboot"),
        ("ASP.NET", ["dotnet", "--info"], "dotnet", "dotnet new web"),
        ("Laravel", ["php", "artisan", "--version"], "php", "composer create-project laravel/laravel"),
        ("Gin", ["go", "list", "-m", "github.com/gin-gonic/gin"], "go", "go get github.com/gin-gonic/gin"),
    ]

    for name, cmd, runtime, install_cmd in checks:
        version = _version(cmd)
        if version:
            frameworks.append({
                "name": name,
                "version": version,
                "runtime": runtime,
                "install_hint": install_cmd,
            })

    return frameworks


def _detect_runtimes() -> list[dict[str, Any]]:
    """Detect installed language runtimes."""
    runtimes: list[dict[str, Any]] = []

    checks = [
        ("Python", ["python3", "--version"], ["python", "--version"]),
        ("Node.js", ["node", "--version"], None),
        ("Java", ["java", "-version"], None),
        ("Go", ["go", "version"], None),
        ("Rust", ["rustc", "--version"], None),
        (".NET", ["dotnet", "--version"], None),
        ("Ruby", ["ruby", "--version"], None),
        ("PHP", ["php", "--version"], None),
        ("Kotlin", ["kotlin", "-version"], None),
        ("Scala", ["scala", "-version"], None),
        ("Elixir", ["elixir", "--version"], None),
        ("Dart", ["dart", "--version"], None),
        ("Swift", ["swift", "--version"], None),
        ("Perl", ["perl", "--version"], None),
        ("R", ["R", "--version"], None),
        ("Julia", ["julia", "--version"], None),
    ]

    for name, primary, fallback in checks:
        version = _version(primary)
        if not version and fallback:
            version = _version(fallback)
        if version:
            runtimes.append({"name": name, "version": version})

    return runtimes


def _detect_package_managers() -> list[dict[str, Any]]:
    """Detect installed package managers."""
    managers: list[dict[str, Any]] = []

    checks = [
        ("pip", ["pip3", "--version"], ["pip", "--version"]),
        ("npm", ["npm", "--version"], None),
        ("yarn", ["yarn", "--version"], None),
        ("pnpm", ["pnpm", "--version"], None),
        ("cargo", ["cargo", "--version"], None),
        ("go modules", ["go", "version"], None),
        ("maven", ["mvn", "--version"], None),
        ("gradle", ["gradle", "--version"], None),
        ("composer", ["composer", "--version"], None),
        ("gem", ["gem", "--version"], None),
        ("nuget", ["nuget", "help"], ["dotnet", "nuget", "--version"]),
        ("apt", ["apt", "--version"], None),
        ("brew", ["brew", "--version"], None),
        ("dnf", ["dnf", "--version"], None),
        ("pacman", ["pacman", "--version"], None),
        ("winget", ["winget", "--version"], None),
        ("choco", ["choco", "--version"], None),
        ("scoop", ["scoop", "--version"], None),
    ]

    for name, primary, fallback in checks:
        version = _version(primary)
        if not version and fallback:
            version = _version(fallback)
        if version:
            managers.append({"name": name, "version": version})

    return managers


def _detect_infra_tools() -> list[dict[str, Any]]:
    """Detect infrastructure and DevOps tools."""
    tools: list[dict[str, Any]] = []

    checks = [
        ("Docker", ["docker", "--version"]),
        ("Docker Compose", ["docker", "compose", "version"]),
        ("kubectl", ["kubectl", "version", "--client", "--short"]),
        ("Helm", ["helm", "version", "--short"]),
        ("Terraform", ["terraform", "--version"]),
        ("Ansible", ["ansible", "--version"]),
        ("AWS CLI", ["aws", "--version"]),
        ("Azure CLI", ["az", "--version"]),
        ("GCloud", ["gcloud", "--version"]),
        ("Git", ["git", "--version"]),
        ("Make", ["make", "--version"]),
        ("CMake", ["cmake", "--version"]),
        ("Nginx", ["nginx", "-v"]),
        ("Apache", ["apache2", "-v"]),
        ("Caddy", ["caddy", "version"]),
    ]

    for name, cmd in checks:
        version = _version(cmd)
        if version:
            tools.append({"name": name, "version": version})

    return tools


def _detect_running_services() -> list[dict[str, str]]:
    """Detect database and app services that are currently running."""
    services: list[dict[str, str]] = []

    if IS_LINUX:
        # Check systemd services
        db_services = [
            "postgresql", "mysql", "mysqld", "mariadb", "mongod", "mongodb",
            "redis", "redis-server", "elasticsearch", "cassandra",
            "nginx", "apache2", "httpd", "docker",
        ]
        for svc in db_services:
            result = _run(["systemctl", "is-active", svc])
            if result == "active":
                services.append({"name": svc, "status": "running"})

    elif IS_MACOS:
        # Check brew services
        output = _run(["brew", "services", "list"])
        if output:
            for line in output.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "started":
                    services.append({"name": parts[0], "status": "running"})

    elif IS_WINDOWS:
        # Check Windows services
        db_services = ["MSSQLSERVER", "MySQL", "PostgreSQL", "MongoDB", "Redis"]
        for svc in db_services:
            result = _run(["sc", "query", svc])
            if "RUNNING" in result:
                services.append({"name": svc, "status": "running"})

    return services


# ── Public API ────────────────────────────────────────────────

def environment_discovery(category: str = "all") -> str:
    """Discover what software is installed and running on this system.

    Args:
        category: What to scan. Options:
            - "all"            — Full scan (databases + runtimes + frameworks + tools + services)
            - "databases"      — Installed/running database engines
            - "runtimes"       — Programming language runtimes
            - "frameworks"     — Web/app framework CLIs
            - "package-managers" — Package managers
            - "infra"          — DevOps/infrastructure tools
            - "services"       — Currently running services
            - "recommend"      — Recommend a stack for a new project

    Returns:
        JSON string with discovery results.
    """
    category = category.lower().strip()

    # In sandbox mode, include Docker service discovery with credentials
    sandbox_services = _detect_sandbox_services() if _is_sandbox() else {}

    if category == "all":
        result = {
            "platform": {
                "os": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "sandbox": _is_sandbox(),
            },
            "databases": _detect_databases(),
            "runtimes": _detect_runtimes(),
            "frameworks": _detect_web_frameworks(),
            "package_managers": _detect_package_managers(),
            "infra_tools": _detect_infra_tools(),
            "running_services": _detect_running_services(),
        }
        if sandbox_services:
            result["sandbox_services"] = sandbox_services
        return json.dumps(result, indent=2)

    elif category == "databases":
        dbs = _detect_databases()
        result_db: dict[str, Any] = {}
        if not dbs:
            result_db = {"databases": [], "note": "No databases detected. SQLite is always available via Python's sqlite3 module."}
        else:
            result_db = {"databases": dbs}
        # In sandbox mode, add connection details
        if sandbox_services:
            db_keys = {"postgres", "mysql", "mongodb", "redis", "elasticsearch"}
            result_db["sandbox_connections"] = {
                k: v for k, v in sandbox_services.items() if k in db_keys
            }
        return json.dumps(result_db, indent=2)

    elif category == "runtimes":
        return json.dumps({"runtimes": _detect_runtimes()}, indent=2)

    elif category == "frameworks":
        return json.dumps({"frameworks": _detect_web_frameworks()}, indent=2)

    elif category in ("package-managers", "package_managers"):
        return json.dumps({"package_managers": _detect_package_managers()}, indent=2)

    elif category == "infra":
        return json.dumps({"infra_tools": _detect_infra_tools()}, indent=2)

    elif category == "services":
        result_svc: dict[str, Any] = {"running_services": _detect_running_services()}
        if sandbox_services:
            result_svc["sandbox_services"] = sandbox_services
        return json.dumps(result_svc, indent=2)

    elif category == "recommend":
        return _build_recommendation()

    else:
        return ('Error: Unknown category. Use: all, databases, runtimes, '
                'frameworks, package-managers, infra, services, recommend')


def _build_recommendation() -> str:
    """Build a stack recommendation based on what's actually available."""
    dbs = _detect_databases()
    runtimes = _detect_runtimes()
    frameworks = _detect_web_frameworks()
    infra = _detect_infra_tools()

    runtime_names = [r["name"] for r in runtimes]
    db_names = [d["name"] for d in dbs]
    running_dbs = [d for d in dbs if d.get("running")]
    framework_names = [f["name"] for f in frameworks]
    infra_names = [t["name"] for t in infra]

    rec: dict[str, Any] = {
        "available": {
            "runtimes": runtime_names,
            "databases": db_names,
            "running_databases": [d["name"] for d in running_dbs],
            "frameworks": framework_names,
            "infra": infra_names,
        },
        "recommendations": {},
    }

    # Database recommendation
    db_priority = ["PostgreSQL", "MySQL", "MariaDB", "MongoDB", "SQLite"]
    recommended_db = None
    for pref in db_priority:
        # Prefer running databases
        running = [d for d in running_dbs if d["name"] == pref]
        if running:
            recommended_db = running[0]
            break
    if not recommended_db:
        for pref in db_priority:
            installed = [d for d in dbs if d["name"] == pref]
            if installed:
                recommended_db = installed[0]
                break
    if not recommended_db:
        recommended_db = {"name": "SQLite", "engine_key": "sqlite", "note": "Built-in, no install needed"}

    rec["recommendations"]["database"] = {
        "primary": recommended_db["name"],
        "engine_key": recommended_db.get("engine_key", "sqlite"),
        "running": recommended_db.get("running", recommended_db["name"] == "SQLite"),
        "reason": f"{'Already running' if recommended_db.get('running') else 'Installed'} on this system"
            if recommended_db["name"] != "SQLite"
            else "Built-in Python module, zero setup needed",
    }

    # Web framework recommendation per runtime
    framework_recs = []
    if "Python" in runtime_names:
        if "FastAPI" in framework_names:
            framework_recs.append({"name": "FastAPI", "runtime": "Python", "reason": "Installed, modern async, auto-docs"})
        elif "Django" in framework_names:
            framework_recs.append({"name": "Django", "runtime": "Python", "reason": "Installed, batteries-included"})
        elif "Flask" in framework_names:
            framework_recs.append({"name": "Flask", "runtime": "Python", "reason": "Installed, lightweight"})
        else:
            framework_recs.append({"name": "FastAPI", "runtime": "Python", "reason": "Best for APIs (pip install fastapi uvicorn)"})

    if "Node.js" in runtime_names:
        if "Next.js" in framework_names:
            framework_recs.append({"name": "Next.js", "runtime": "Node.js", "reason": "Installed, full-stack React"})
        elif "Express.js" in framework_names:
            framework_recs.append({"name": "Express.js", "runtime": "Node.js", "reason": "Installed, lightweight API server"})
        else:
            framework_recs.append({"name": "Express.js", "runtime": "Node.js", "reason": "Industry standard (npm install express)"})

    if "Java" in runtime_names:
        if "Spring Boot" in framework_names:
            framework_recs.append({"name": "Spring Boot", "runtime": "Java", "reason": "Installed, enterprise-grade"})

    if ".NET" in runtime_names:
        framework_recs.append({"name": "ASP.NET", "runtime": ".NET", "reason": "Built into .NET SDK"})

    if "Go" in runtime_names:
        framework_recs.append({"name": "Gin", "runtime": "Go", "reason": "Fast, lightweight HTTP framework"})

    rec["recommendations"]["frameworks"] = framework_recs

    # Container recommendation
    has_docker = "Docker" in infra_names
    has_k8s = "kubectl" in infra_names
    rec["recommendations"]["deployment"] = {
        "docker": has_docker,
        "kubernetes": has_k8s,
        "suggestion": "Docker + Kubernetes" if has_docker and has_k8s
            else "Docker containers" if has_docker
            else "Direct deployment (no container runtime found)",
    }

    return json.dumps(rec, indent=2)
