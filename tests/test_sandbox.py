"""Tests for sandbox-related features: discovery, secrets, masking."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from pyoz.tools.discovery_tools import (
    _is_sandbox,
    _mask_password,
    _read_secret_file,
    _load_db_credentials,
    _get_credential,
    _detect_sandbox_services,
    _tcp_check,
    environment_discovery,
)


class TestSandboxDetection(unittest.TestCase):
    """Test _is_sandbox() flag detection."""

    def test_not_sandbox_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_is_sandbox())

    def test_sandbox_when_flag_set(self):
        with patch.dict(os.environ, {"PYOZ_SANDBOX": "1"}):
            self.assertTrue(_is_sandbox())

    def test_sandbox_flag_must_be_1(self):
        with patch.dict(os.environ, {"PYOZ_SANDBOX": "true"}):
            self.assertFalse(_is_sandbox())
        with patch.dict(os.environ, {"PYOZ_SANDBOX": "0"}):
            self.assertFalse(_is_sandbox())


class TestPasswordMasking(unittest.TestCase):
    """Test _mask_password() hides credentials."""

    def test_mask_normal_password(self):
        result = _mask_password("pyoz_secret_password")
        self.assertEqual(result, "py****")
        self.assertNotIn("secret", result)

    def test_mask_short_password(self):
        result = _mask_password("abc")
        self.assertEqual(result, "****")

    def test_mask_empty_password(self):
        result = _mask_password("")
        self.assertEqual(result, "(not set)")

    def test_mask_exact_4_chars(self):
        result = _mask_password("abcd")
        self.assertEqual(result, "****")

    def test_mask_5_chars(self):
        result = _mask_password("abcde")
        self.assertEqual(result, "ab****")


class TestSecretFileReading(unittest.TestCase):
    """Test _read_secret_file() reads Docker secrets."""

    def test_read_existing_secret(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("sk-ant-my-secret-key")
            f.flush()
            result = _read_secret_file(f.name)
            self.assertEqual(result, "sk-ant-my-secret-key")
        os.unlink(f.name)

    def test_read_nonexistent_file(self):
        result = _read_secret_file("/nonexistent/path/secret.txt")
        self.assertEqual(result, "")

    def test_read_strips_whitespace(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("  my-key-with-spaces  \n")
            f.flush()
            result = _read_secret_file(f.name)
            self.assertEqual(result, "my-key-with-spaces")
        os.unlink(f.name)


class TestDbCredentials(unittest.TestCase):
    """Test _load_db_credentials() from JSON file."""

    def test_load_valid_json(self):
        creds = {
            "postgres_user": "pyoz",
            "postgres_password": "strong_pass_123",
            "mysql_user": "pyoz",
            "mysql_password": "another_pass",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(creds, f)
            f.flush()
            with patch.dict(os.environ, {"DB_CREDENTIALS_FILE": f.name}):
                result = _load_db_credentials()
                self.assertEqual(result["postgres_password"], "strong_pass_123")
                self.assertEqual(result["mysql_user"], "pyoz")
        os.unlink(f.name)

    def test_load_nonexistent_file(self):
        with patch.dict(os.environ, {"DB_CREDENTIALS_FILE": "/nonexistent.json"}):
            result = _load_db_credentials()
            self.assertEqual(result, {})

    def test_load_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            f.flush()
            with patch.dict(os.environ, {"DB_CREDENTIALS_FILE": f.name}):
                result = _load_db_credentials()
                self.assertEqual(result, {})
        os.unlink(f.name)


class TestGetCredential(unittest.TestCase):
    """Test _get_credential() priority: secrets file > env var > default."""

    def test_prefers_secret_file_value(self):
        creds = {"postgres_password": "from_secret"}
        with patch.dict(os.environ, {"POSTGRES_PASSWORD": "from_env"}):
            result = _get_credential(creds, "postgres_password", "POSTGRES_PASSWORD", "default")
            self.assertEqual(result, "from_secret")

    def test_falls_back_to_env_var(self):
        creds = {}
        with patch.dict(os.environ, {"POSTGRES_PASSWORD": "from_env"}):
            result = _get_credential(creds, "postgres_password", "POSTGRES_PASSWORD", "default")
            self.assertEqual(result, "from_env")

    def test_falls_back_to_default(self):
        creds = {}
        with patch.dict(os.environ, {}, clear=True):
            result = _get_credential(creds, "postgres_password", "POSTGRES_PASSWORD", "default_val")
            self.assertEqual(result, "default_val")

    def test_empty_secret_falls_to_env(self):
        creds = {"postgres_password": ""}
        with patch.dict(os.environ, {"POSTGRES_PASSWORD": "from_env"}):
            result = _get_credential(creds, "postgres_password", "POSTGRES_PASSWORD", "default")
            self.assertEqual(result, "from_env")


class TestTcpCheck(unittest.TestCase):
    """Test _tcp_check() network connectivity."""

    def test_unreachable_host(self):
        # Should return False for non-existent host
        result = _tcp_check("nonexistent.invalid.host.example", 5432, timeout=1)
        self.assertFalse(result)

    def test_closed_port(self):
        # Port 1 is almost never open
        result = _tcp_check("127.0.0.1", 1, timeout=1)
        self.assertFalse(result)


class TestSandboxServiceDetection(unittest.TestCase):
    """Test _detect_sandbox_services() reads env vars correctly."""

    def setUp(self):
        """Mock TCP checks to avoid real network calls and DNS timeouts."""
        self._tcp_patcher = patch(
            "pyoz.tools.discovery_tools._tcp_check", return_value=False
        )
        self._tcp_patcher.start()

    def tearDown(self):
        self._tcp_patcher.stop()

    def _sandbox_env(self):
        """Return a dict simulating sandbox environment variables."""
        return {
            "PYOZ_SANDBOX": "1",
            "POSTGRES_HOST": "postgres",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "pyoz",
            "POSTGRES_PASSWORD": "test_pg_pass",
            "POSTGRES_DB": "app_db",
            "DATABASE_URL": "postgresql://pyoz:test_pg_pass@postgres:5432/app_db",
            "MYSQL_HOST": "mysql",
            "MYSQL_PORT": "3306",
            "MYSQL_USER": "pyoz",
            "MYSQL_PASSWORD": "test_mysql_pass",
            "MYSQL_DATABASE": "app_db",
            "REDIS_HOST": "redis",
            "REDIS_PORT": "6379",
            "REDIS_PASSWORD": "",
            "REDIS_URL": "redis://redis:6379",
            "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
            "MONGO_HOST": "mongodb",
            "MONGO_PORT": "27017",
            "MONGO_USER": "pyoz",
            "MONGO_PASSWORD": "test_mongo_pass",
            "MONGO_DB": "app_db",
            "RABBITMQ_HOST": "rabbitmq",
            "RABBITMQ_PORT": "5672",
            "RABBITMQ_USER": "pyoz",
            "RABBITMQ_PASSWORD": "test_rabbit_pass",
            "ELASTICSEARCH_HOST": "elasticsearch",
            "ELASTICSEARCH_PORT": "9200",
            "ELASTICSEARCH_URL": "http://elasticsearch:9200",
            "MINIO_ENDPOINT": "minio:9000",
            "MINIO_ACCESS_KEY": "pyoz",
            "MINIO_SECRET_KEY": "test_minio_secret",
            "DB_CREDENTIALS_FILE": "/nonexistent.json",  # Force env var fallback
        }

    def test_detects_all_services(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            services = _detect_sandbox_services(mask_secrets=False)
            self.assertIn("postgres", services)
            self.assertIn("mysql", services)
            self.assertIn("redis", services)
            self.assertIn("kafka", services)
            self.assertIn("mongodb", services)
            self.assertIn("rabbitmq", services)
            self.assertIn("elasticsearch", services)
            self.assertIn("minio", services)

    def test_postgres_details(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            services = _detect_sandbox_services(mask_secrets=False)
            pg = services["postgres"]
            self.assertEqual(pg["host"], "postgres")
            self.assertEqual(pg["port"], 5432)
            self.assertEqual(pg["user"], "pyoz")
            self.assertEqual(pg["database"], "app_db")
            self.assertEqual(pg["engine_key"], "postgres")

    def test_passwords_masked_by_default(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            services = _detect_sandbox_services(mask_secrets=True)
            # Passwords should be masked
            self.assertEqual(services["postgres"]["password"], "te****")
            self.assertEqual(services["mysql"]["password"], "te****")
            self.assertEqual(services["mongodb"]["password"], "te****")
            self.assertEqual(services["minio"]["secret_key"], "te****")

    def test_passwords_unmasked_when_requested(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            services = _detect_sandbox_services(mask_secrets=False)
            self.assertEqual(services["postgres"]["password"], "test_pg_pass")
            self.assertEqual(services["mysql"]["password"], "test_mysql_pass")

    def test_kafka_bootstrap_parsing(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            services = _detect_sandbox_services()
            kafka = services["kafka"]
            self.assertEqual(kafka["host"], "kafka")
            self.assertEqual(kafka["port"], 9092)
            self.assertEqual(kafka["bootstrap_servers"], "kafka:9092")

    def test_minio_endpoint_parsing(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            services = _detect_sandbox_services(mask_secrets=False)
            minio = services["minio"]
            self.assertEqual(minio["host"], "minio")
            self.assertEqual(minio["port"], 9000)
            self.assertEqual(minio["access_key"], "pyoz")

    def test_no_services_without_env_vars(self):
        with patch.dict(os.environ, {"PYOZ_SANDBOX": "1", "DB_CREDENTIALS_FILE": "/nonexistent.json"}, clear=True):
            services = _detect_sandbox_services()
            self.assertEqual(services, {})

    def test_running_status_false_for_unreachable(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            services = _detect_sandbox_services()
            # These hosts don't exist in this environment
            self.assertFalse(services["postgres"]["running"])
            self.assertFalse(services["redis"]["running"])
            self.assertFalse(services["kafka"]["running"])

    def test_redis_no_auth_display(self):
        env = self._sandbox_env()
        env["REDIS_PASSWORD"] = ""
        with patch.dict(os.environ, env, clear=True):
            services = _detect_sandbox_services(mask_secrets=True)
            self.assertEqual(services["redis"]["password"], "(no auth)")


class TestEnvironmentDiscoveryWithSandbox(unittest.TestCase):
    """Test that environment_discovery() includes sandbox info."""

    def setUp(self):
        self._tcp_patcher = patch(
            "pyoz.tools.discovery_tools._tcp_check", return_value=False
        )
        self._tcp_patcher.start()

    def tearDown(self):
        self._tcp_patcher.stop()

    def _sandbox_env(self):
        return {
            "PYOZ_SANDBOX": "1",
            "POSTGRES_HOST": "postgres",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "pyoz",
            "POSTGRES_PASSWORD": "secret123",
            "POSTGRES_DB": "testdb",
            "REDIS_HOST": "redis",
            "REDIS_PORT": "6379",
            "REDIS_PASSWORD": "",
            "DB_CREDENTIALS_FILE": "/nonexistent.json",
        }

    def test_all_category_includes_sandbox_services(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            result = json.loads(environment_discovery("all"))
            self.assertTrue(result["platform"]["sandbox"])
            self.assertIn("sandbox_services", result)
            self.assertIn("postgres", result["sandbox_services"])

    def test_all_category_masks_passwords(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            result = json.loads(environment_discovery("all"))
            pg = result["sandbox_services"]["postgres"]
            self.assertEqual(pg["password"], "se****")
            self.assertNotIn("secret123", json.dumps(result))

    def test_databases_category_includes_sandbox_connections(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            result = json.loads(environment_discovery("databases"))
            self.assertIn("sandbox_connections", result)
            self.assertIn("postgres", result["sandbox_connections"])

    def test_services_category_includes_sandbox(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            result = json.loads(environment_discovery("services"))
            self.assertIn("sandbox_services", result)

    def test_no_sandbox_flag_no_sandbox_services(self):
        with patch.dict(os.environ, {}, clear=True):
            result = json.loads(environment_discovery("all"))
            self.assertFalse(result["platform"]["sandbox"])
            self.assertNotIn("sandbox_services", result)

    def test_password_never_leaks_in_any_category(self):
        with patch.dict(os.environ, self._sandbox_env(), clear=True):
            for category in ["all", "databases", "services"]:
                result_str = environment_discovery(category)
                self.assertNotIn("secret123", result_str,
                    f"Password leaked in category '{category}'!")


class TestCredentialFileIntegration(unittest.TestCase):
    """Test that credentials from JSON file take priority and get masked."""

    def setUp(self):
        self._tcp_patcher = patch(
            "pyoz.tools.discovery_tools._tcp_check", return_value=False
        )
        self._tcp_patcher.start()

    def tearDown(self):
        self._tcp_patcher.stop()

    def test_secret_file_overrides_env_var(self):
        creds = {
            "postgres_user": "secret_user",
            "postgres_password": "secret_pass_from_file",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(creds, f)
            f.flush()
            env = {
                "PYOZ_SANDBOX": "1",
                "POSTGRES_HOST": "postgres",
                "POSTGRES_PORT": "5432",
                "POSTGRES_USER": "env_user",
                "POSTGRES_PASSWORD": "env_pass",
                "POSTGRES_DB": "testdb",
                "DB_CREDENTIALS_FILE": f.name,
            }
            with patch.dict(os.environ, env, clear=True):
                services = _detect_sandbox_services(mask_secrets=False)
                # Secret file value should win
                self.assertEqual(services["postgres"]["user"], "secret_user")
                self.assertEqual(services["postgres"]["password"], "secret_pass_from_file")
        os.unlink(f.name)

    def test_secret_file_passwords_get_masked(self):
        creds = {"postgres_password": "super_secret_password_123"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(creds, f)
            f.flush()
            env = {
                "PYOZ_SANDBOX": "1",
                "POSTGRES_HOST": "postgres",
                "POSTGRES_PORT": "5432",
                "POSTGRES_DB": "testdb",
                "DB_CREDENTIALS_FILE": f.name,
            }
            with patch.dict(os.environ, env, clear=True):
                services = _detect_sandbox_services(mask_secrets=True)
                self.assertEqual(services["postgres"]["password"], "su****")
                self.assertNotIn("super_secret", json.dumps(services))
        os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
