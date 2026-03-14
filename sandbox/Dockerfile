# ============================================================================
# PyOz Enterprise Sandbox — Agent Image
# All languages, runtimes, CLI tools, and DB clients pre-installed.
# The agent runs here; databases/services run in separate compose containers.
# ============================================================================

FROM ubuntu:24.04

LABEL maintainer="pyoz-sandbox"
LABEL description="PyOz AI Agent with all enterprise runtimes and tools"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# ── Base system packages ─────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    wget \
    git \
    unzip \
    zip \
    jq \
    tree \
    htop \
    vim \
    nano \
    sudo \
    gnupg \
    lsb-release \
    software-properties-common \
    apt-transport-https \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# ── Python 3.12 ──────────────────────────────────────────────
RUN add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && rm -rf /var/lib/apt/lists/*

# Install pip into Python 3.12 (system pip belongs to the distro Python;
# --ignore-installed avoids the "Cannot uninstall pip, RECORD not found" error)
RUN python3 -m pip install --break-system-packages --ignore-installed pip setuptools wheel

# ── Node.js 22 LTS ───────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g yarn pnpm && \
    rm -rf /var/lib/apt/lists/*

# ── Java 21 (Eclipse Temurin) ────────────────────────────────
RUN curl -fsSL https://packages.adoptium.net/artifactory/api/gpg/key/public | gpg --dearmor -o /usr/share/keyrings/adoptium.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb $(lsb_release -cs) main" \
    > /etc/apt/sources.list.d/adoptium.list && \
    apt-get update && apt-get install -y temurin-21-jdk && \
    rm -rf /var/lib/apt/lists/*

# JAVA_HOME is architecture-dependent
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
      ln -s /usr/lib/jvm/temurin-21-jdk-amd64 /usr/lib/jvm/temurin-21-jdk; \
    elif [ "$ARCH" = "arm64" ]; then \
      ln -s /usr/lib/jvm/temurin-21-jdk-arm64 /usr/lib/jvm/temurin-21-jdk; \
    fi
ENV JAVA_HOME=/usr/lib/jvm/temurin-21-jdk

# ── Maven & Gradle ───────────────────────────────────────────
ARG MAVEN_VERSION=3.9.9
RUN curl -fsSL https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz \
    | tar xz -C /opt && \
    ln -s /opt/apache-maven-${MAVEN_VERSION}/bin/mvn /usr/local/bin/mvn

ARG GRADLE_VERSION=8.10
RUN curl -fsSL https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip -o /tmp/gradle.zip && \
    unzip -q /tmp/gradle.zip -d /opt && \
    ln -s /opt/gradle-${GRADLE_VERSION}/bin/gradle /usr/local/bin/gradle && \
    rm /tmp/gradle.zip

# ── Go 1.22 ──────────────────────────────────────────────────
ARG GO_VERSION=1.22.7
RUN ARCH=$(dpkg --print-architecture) && \
    curl -fsSL https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz | tar xz -C /usr/local
ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"
ENV GOPATH=/root/go

# ── Rust (latest stable) ────────────────────────────────────
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# ── .NET 8 SDK ───────────────────────────────────────────────
RUN curl -fsSL https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb -o /tmp/ms.deb && \
    dpkg -i /tmp/ms.deb && rm /tmp/ms.deb && \
    apt-get update && apt-get install -y dotnet-sdk-8.0 && \
    rm -rf /var/lib/apt/lists/*

# ── Ruby 3.3 ─────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ruby-full && \
    rm -rf /var/lib/apt/lists/*

# ── PHP 8.3 + Composer ──────────────────────────────────────
RUN add-apt-repository ppa:ondrej/php -y && \
    apt-get update && apt-get install -y --no-install-recommends \
    php8.3 php8.3-cli php8.3-common php8.3-curl php8.3-mbstring \
    php8.3-xml php8.3-zip php8.3-mysql php8.3-pgsql php8.3-sqlite3 && \
    curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer && \
    rm -rf /var/lib/apt/lists/*

# ── Database CLI clients ─────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    mysql-client \
    sqlite3 \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# MongoDB Shell (mongosh)
RUN curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/mongodb.gpg] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" \
    > /etc/apt/sources.list.d/mongodb.list && \
    apt-get update && apt-get install -y mongodb-mongosh && \
    rm -rf /var/lib/apt/lists/*

# ── Kafka CLI tools ──────────────────────────────────────────
ARG KAFKA_VERSION=3.7.1
RUN curl -fsSL https://archive.apache.org/dist/kafka/${KAFKA_VERSION}/kafka_2.13-${KAFKA_VERSION}.tgz \
    | tar xz -C /opt && \
    ln -s /opt/kafka_2.13-${KAFKA_VERSION} /opt/kafka
ENV PATH="/opt/kafka/bin:${PATH}"

# ── Infrastructure CLI tools ─────────────────────────────────

# Docker CLI (talks to host Docker via socket mount)
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y docker-ce-cli docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

# kubectl (multi-arch)
RUN ARCH=$(dpkg --print-architecture) && \
    curl -fsSL "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/${ARCH}/kubectl" \
    -o /usr/local/bin/kubectl && chmod +x /usr/local/bin/kubectl

# Helm (auto-detects arch)
RUN curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Terraform (multi-arch)
RUN ARCH=$(dpkg --print-architecture) && \
    curl -fsSL "https://releases.hashicorp.com/terraform/1.9.5/terraform_1.9.5_linux_${ARCH}.zip" -o /tmp/tf.zip && \
    unzip -q /tmp/tf.zip -d /usr/local/bin && rm /tmp/tf.zip

# yq (multi-arch)
RUN ARCH=$(dpkg --print-architecture) && \
    curl -fsSL "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_${ARCH}" -o /usr/local/bin/yq && \
    chmod +x /usr/local/bin/yq

# ── Python DB drivers (for PyOz database_tool) ──────────────
RUN python3 -m pip install --break-system-packages \
    psycopg2-binary \
    mysql-connector-python \
    pymongo \
    redis \
    pymssql \
    elasticsearch \
    confluent-kafka \
    httpx \
    rich \
    prompt_toolkit

# ── Install PyOz agent ───────────────────────────────────────
COPY . /opt/pyoz
WORKDIR /opt/pyoz
RUN python3 -m pip install --break-system-packages -e .

# ── Workspace setup ──────────────────────────────────────────
RUN mkdir -p /workspace /root/.pyoz
WORKDIR /workspace

# ── Entrypoint ───────────────────────────────────────────────
COPY sandbox/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
