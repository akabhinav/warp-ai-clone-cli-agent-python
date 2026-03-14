"""Context tools — codebase index and static configs."""

from typing import Any


# Static project configs for common languages
STATIC_CONFIGS: dict[str, dict[str, str]] = {
    "java": {
        "file": "pom.xml",
        "content": """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.{project_name}</groupId>
    <artifactId>{project_name}</artifactId>
    <version>1.0-SNAPSHOT</version>
    <packaging>jar</packaging>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>5.10.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.12.1</version>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.2.5</version>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-jar-plugin</artifactId>
                <version>3.3.0</version>
                <configuration>
                    <archive>
                        <manifest>
                            <mainClass>com.{project_name}.App</mainClass>
                        </manifest>
                    </archive>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>""",
    },
    "python": {
        "file": "requirements.txt",
        "content": """# {project_name} dependencies
""",
    },
    "go": {
        "file": "go.mod",
        "content": """module {project_name}

go 1.21
""",
    },
    "rust": {
        "file": "Cargo.toml",
        "content": """[package]
name = "{project_name}"
version = "0.1.0"
edition = "2021"

[dependencies]
""",
    },
    "javascript": {
        "file": "package.json",
        "content": """{
  "name": "{project_name}",
  "version": "1.0.0",
  "description": "",
  "main": "index.js",
  "scripts": {
    "start": "node index.js",
    "test": "jest"
  },
  "dependencies": {},
  "devDependencies": {
    "jest": "^29.7.0"
  }
}""",
    },
    "typescript": {
        "file": "package.json",
        "content": """{
  "name": "{project_name}",
  "version": "1.0.0",
  "description": "",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "test": "jest"
  },
  "dependencies": {},
  "devDependencies": {
    "typescript": "^5.4.0",
    "jest": "^29.7.0",
    "ts-jest": "^29.1.0",
    "@types/jest": "^29.5.0"
  }
}""",
    },
    "kotlin": {
        "file": "build.gradle.kts",
        "content": """plugins {
    kotlin("jvm") version "1.9.22"
    application
}

group = "com.{project_name}"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(kotlin("test"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
}

tasks.test {
    useJUnitPlatform()
}

application {
    mainClass.set("com.{project_name}.AppKt")
}
""",
    },
    "csharp": {
        "file": "{project_name}.csproj",
        "content": """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <RootNamespace>{project_name}</RootNamespace>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.9.0" />
    <PackageReference Include="xunit" Version="2.7.0" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.7" />
  </ItemGroup>
</Project>""",
    },
}


def static_config(language: str, project_name: str) -> str:
    """Return known-good build config for the given language."""
    lang = language.lower().strip()
    if lang not in STATIC_CONFIGS:
        available = ", ".join(sorted(STATIC_CONFIGS.keys()))
        raise ValueError(f"No static config for '{lang}'. Available: {available}")
    config = STATIC_CONFIGS[lang]
    content = config["content"].replace("{project_name}", project_name)
    filename = config["file"].replace("{project_name}", project_name)
    return f"# File: {filename}\n{content}"


def codebase_index(index_data: dict[str, Any] | None = None) -> str:
    """Return AST-structured summary of all indexed files."""
    if not index_data:
        return "No files indexed yet."

    lines = []
    for filepath, info in sorted(index_data.items()):
        lines.append(f"\nFILE: {filepath}")
        if isinstance(info, dict):
            for symbol in info.get("symbols", []):
                kind = symbol.get("kind", "unknown")
                name = symbol.get("name", "?")
                detail = symbol.get("detail", "")
                indent = "  " if kind in ("class", "struct", "interface", "enum", "module") else "    "
                if detail:
                    lines.append(f"{indent}{kind} {name}: {detail}")
                else:
                    lines.append(f"{indent}{kind} {name}")
            if info.get("imports"):
                lines.append(f"  imports: {', '.join(info['imports'][:20])}")
            if info.get("dependencies"):
                lines.append(f"  depends on: {', '.join(info['dependencies'][:20])}")
        elif isinstance(info, str):
            lines.append(f"  {info}")

    return "\n".join(lines) if lines else "No files indexed yet."
