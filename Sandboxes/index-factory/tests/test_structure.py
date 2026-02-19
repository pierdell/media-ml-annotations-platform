"""
Structural validation tests for index-factory sandbox.
These tests verify file presence, code structure, SQL syntax,
and consistency without requiring external dependencies.
"""
import os
import re
import json
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestProjectStructure(unittest.TestCase):
    """Verify that all required files and directories exist."""

    REQUIRED_FILES = [
        "docker-compose.yml",
        ".env.example",
        "scripts/init-db.sql",
        "nginx/default.conf",
        # Backend
        "backend/Dockerfile",
        "backend/requirements.txt",
        "backend/app/__init__.py",
        "backend/app/main.py",
        "backend/app/config.py",
        "backend/app/database.py",
        "backend/app/api/__init__.py",
        "backend/app/api/auth.py",
        "backend/app/api/objects.py",
        "backend/app/api/documents.py",
        "backend/app/api/media.py",
        "backend/app/api/search.py",
        "backend/app/api/categories.py",
        "backend/app/models/__init__.py",
        "backend/app/models/user.py",
        "backend/app/models/object.py",
        "backend/app/models/ontology.py",
        "backend/app/models/reference_media.py",
        "backend/app/models/document.py",
        "backend/app/models/category_assignment.py",
        "backend/app/schemas/__init__.py",
        "backend/app/schemas/auth.py",
        "backend/app/schemas/objects.py",
        "backend/app/schemas/documents.py",
        "backend/app/schemas/search.py",
        "backend/app/services/__init__.py",
        "backend/app/services/auth.py",
        "backend/app/services/indexing.py",
        "backend/app/services/qdrant_service.py",
        # Worker
        "worker/Dockerfile",
        "worker/requirements.txt",
        "worker/celery_app.py",
        "worker/tasks/__init__.py",
        "worker/tasks/indexing.py",
        # Frontend
        "frontend/Dockerfile",
        "frontend/package.json",
        "frontend/index.html",
        "frontend/tsconfig.json",
        "frontend/vite.config.ts",
        "frontend/tailwind.config.js",
        "frontend/postcss.config.js",
        "frontend/nginx.conf",
        "frontend/src/main.tsx",
        "frontend/src/App.tsx",
        "frontend/src/index.css",
        "frontend/src/lib/api.ts",
        "frontend/src/hooks/useAuth.ts",
        "frontend/src/types/index.ts",
        "frontend/src/components/Layout.tsx",
        "frontend/src/pages/LoginPage.tsx",
        "frontend/src/pages/DashboardPage.tsx",
        "frontend/src/pages/ObjectDetailPage.tsx",
        "frontend/src/pages/SearchPage.tsx",
        "frontend/src/pages/DocumentsPage.tsx",
    ]

    def test_all_required_files_exist(self):
        missing = []
        for f in self.REQUIRED_FILES:
            if not (ROOT / f).exists():
                missing.append(f)
        self.assertEqual(missing, [], f"Missing files: {missing}")


class TestDockerCompose(unittest.TestCase):
    """Validate docker-compose.yml structure."""

    def setUp(self):
        self.content = (ROOT / "docker-compose.yml").read_text()

    def test_required_services(self):
        required = ["postgres", "qdrant", "rabbitmq", "redis", "api", "worker", "frontend", "nginx"]
        for svc in required:
            self.assertIn(f"  {svc}:", self.content, f"Missing service: {svc}")

    def test_volumes_defined(self):
        for vol in ["pg_data", "qdrant_data", "rabbitmq_data", "redis_data", "upload_data"]:
            self.assertIn(vol, self.content, f"Missing volume: {vol}")

    def test_healthchecks(self):
        self.assertGreater(self.content.count("healthcheck:"), 2, "Expected healthchecks for infrastructure services")

    def test_network_defined(self):
        self.assertIn("indexfactory:", self.content)


class TestSQLSchema(unittest.TestCase):
    """Validate init-db.sql structure."""

    def setUp(self):
        self.sql = (ROOT / "scripts" / "init-db.sql").read_text()

    def test_required_tables(self):
        tables = ["users", "objects", "ontology_nodes", "reference_media", "documents", "document_chunks", "category_assignments"]
        for table in tables:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", self.sql, f"Missing table: {table}")

    def test_foreign_keys(self):
        self.assertIn("REFERENCES users(id)", self.sql)
        self.assertIn("REFERENCES objects(id)", self.sql)
        self.assertIn("REFERENCES documents(id)", self.sql)
        self.assertIn("REFERENCES ontology_nodes(id)", self.sql)

    def test_indexes_created(self):
        index_count = self.sql.count("CREATE INDEX")
        self.assertGreaterEqual(index_count, 5, f"Expected at least 5 indexes, found {index_count}")

    def test_extensions(self):
        self.assertIn("uuid-ossp", self.sql)
        self.assertIn("pg_trgm", self.sql)

    def test_uuid_primary_keys(self):
        pk_count = self.sql.count("UUID PRIMARY KEY DEFAULT uuid_generate_v4()")
        self.assertGreaterEqual(pk_count, 6, "Expected UUID PKs for all tables")


class TestPythonSyntax(unittest.TestCase):
    """Verify all Python files parse correctly."""

    def test_backend_python_files(self):
        errors = []
        for py_file in (ROOT / "backend").rglob("*.py"):
            try:
                ast.parse(py_file.read_text())
            except SyntaxError as e:
                errors.append(f"{py_file.relative_to(ROOT)}: {e}")
        self.assertEqual(errors, [], f"Python syntax errors:\n" + "\n".join(errors))

    def test_worker_python_files(self):
        errors = []
        for py_file in (ROOT / "worker").rglob("*.py"):
            try:
                ast.parse(py_file.read_text())
            except SyntaxError as e:
                errors.append(f"{py_file.relative_to(ROOT)}: {e}")
        self.assertEqual(errors, [], f"Python syntax errors:\n" + "\n".join(errors))


class TestBackendModels(unittest.TestCase):
    """Check that backend models define expected fields."""

    def _get_class_attrs(self, filepath: str, classname: str) -> list[str]:
        tree = ast.parse((ROOT / filepath).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == classname:
                attrs = []
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        attrs.append(item.target.id)
                return attrs
        return []

    def test_user_model(self):
        attrs = self._get_class_attrs("backend/app/models/user.py", "User")
        for field in ["id", "email", "username", "password_hash"]:
            self.assertIn(field, attrs, f"User missing field: {field}")

    def test_object_model(self):
        attrs = self._get_class_attrs("backend/app/models/object.py", "Object")
        for field in ["id", "user_id", "name", "description"]:
            self.assertIn(field, attrs, f"Object missing field: {field}")

    def test_ontology_node_model(self):
        attrs = self._get_class_attrs("backend/app/models/ontology.py", "OntologyNode")
        for field in ["id", "object_id", "parent_id", "name", "color"]:
            self.assertIn(field, attrs, f"OntologyNode missing field: {field}")

    def test_document_model(self):
        attrs = self._get_class_attrs("backend/app/models/document.py", "Document")
        for field in ["id", "user_id", "source_type", "raw_text", "indexed"]:
            self.assertIn(field, attrs, f"Document missing field: {field}")

    def test_reference_media_model(self):
        attrs = self._get_class_attrs("backend/app/models/reference_media.py", "ReferenceMedia")
        for field in ["id", "object_id", "file_path", "file_name", "indexed"]:
            self.assertIn(field, attrs, f"ReferenceMedia missing field: {field}")


class TestBackendAPI(unittest.TestCase):
    """Verify API routes define expected endpoints."""

    def _find_decorators(self, filepath: str) -> list[str]:
        """Extract route decorator strings like @router.get('/...')"""
        content = (ROOT / filepath).read_text()
        pattern = r'@router\.(get|post|patch|put|delete)\(["\']([^"\']+)'
        return [(method, path) for method, path in re.findall(pattern, content)]

    def test_auth_routes(self):
        routes = self._find_decorators("backend/app/api/auth.py")
        paths = [p for _, p in routes]
        self.assertIn("/register", paths)
        self.assertIn("/login", paths)
        self.assertIn("/me", paths)

    def test_objects_routes(self):
        routes = self._find_decorators("backend/app/api/objects.py")
        methods_paths = [(m, p) for m, p in routes]
        self.assertIn(("get", "/"), methods_paths)
        self.assertIn(("post", "/"), methods_paths)
        self.assertIn(("get", "/{object_id}"), methods_paths)

    def test_documents_routes(self):
        routes = self._find_decorators("backend/app/api/documents.py")
        paths = [p for _, p in routes]
        self.assertIn("/", paths)
        self.assertIn("/upload", paths)

    def test_search_route(self):
        routes = self._find_decorators("backend/app/api/search.py")
        self.assertTrue(any(m == "post" for m, _ in routes), "Search should have POST endpoint")

    def test_categories_routes(self):
        routes = self._find_decorators("backend/app/api/categories.py")
        paths = [p for _, p in routes]
        self.assertIn("/", paths)


class TestFrontend(unittest.TestCase):
    """Validate frontend configuration and structure."""

    def test_package_json_valid(self):
        pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
        self.assertEqual(pkg["name"], "index-factory-ui")
        self.assertIn("react", pkg["dependencies"])
        self.assertIn("react-dom", pkg["dependencies"])
        self.assertIn("react-router-dom", pkg["dependencies"])
        self.assertIn("lucide-react", pkg["dependencies"])
        self.assertIn("typescript", pkg["devDependencies"])
        self.assertIn("tailwindcss", pkg["devDependencies"])

    def test_tsconfig_valid(self):
        tsconfig = json.loads((ROOT / "frontend" / "tsconfig.json").read_text())
        self.assertEqual(tsconfig["compilerOptions"]["jsx"], "react-jsx")
        self.assertTrue(tsconfig["compilerOptions"]["strict"])

    def test_vite_config_has_proxy(self):
        content = (ROOT / "frontend" / "vite.config.ts").read_text()
        self.assertIn("proxy", content)
        self.assertIn("/api", content)

    def test_tailwind_config(self):
        content = (ROOT / "frontend" / "tailwind.config.js").read_text()
        self.assertIn("darkMode", content)
        self.assertIn("brand", content)

    def test_index_html_has_root(self):
        content = (ROOT / "frontend" / "index.html").read_text()
        self.assertIn('id="root"', content)
        self.assertIn("main.tsx", content)

    def test_api_client_completeness(self):
        content = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text()
        for method in ["register", "login", "me", "listObjects", "createObject", "search",
                       "listDocuments", "createDocument", "uploadMedia", "listMedia"]:
            self.assertIn(method, content, f"API client missing method: {method}")

    def test_types_defined(self):
        content = (ROOT / "frontend" / "src" / "types" / "index.ts").read_text()
        for type_name in ["User", "IndexObject", "OntologyNode", "ReferenceMedia", "Document",
                          "SearchResult", "SearchResponse", "CategoryAssignment"]:
            self.assertIn(f"export interface {type_name}", content, f"Missing type: {type_name}")


class TestTypeScriptSyntax(unittest.TestCase):
    """Basic TSX/TS syntax validation (bracket matching, import checking)."""

    def _check_bracket_balance(self, filepath: Path) -> bool:
        content = filepath.read_text()
        # Remove strings and template literals (don't match across newlines)
        content = re.sub(r"'[^'\n]*'", "", content)
        content = re.sub(r'"[^"\n]*"', "", content)
        content = re.sub(r"`[^`]*`", "", content, flags=re.DOTALL)
        # Remove comments
        content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)

        stack = []
        pairs = {")": "(", "]": "[", "}": "{"}
        for ch in content:
            if ch in "([{":
                stack.append(ch)
            elif ch in ")]}":
                if not stack or stack[-1] != pairs[ch]:
                    return False
                stack.pop()
        return len(stack) == 0

    def test_tsx_bracket_balance(self):
        errors = []
        for tsx_file in (ROOT / "frontend" / "src").rglob("*.tsx"):
            if not self._check_bracket_balance(tsx_file):
                errors.append(str(tsx_file.relative_to(ROOT)))
        self.assertEqual(errors, [], f"Bracket imbalance in: {errors}")

    def test_ts_bracket_balance(self):
        errors = []
        for ts_file in (ROOT / "frontend" / "src").rglob("*.ts"):
            if not self._check_bracket_balance(ts_file):
                errors.append(str(ts_file.relative_to(ROOT)))
        self.assertEqual(errors, [], f"Bracket imbalance in: {errors}")

    def test_imports_present(self):
        """Check that main component files have react imports."""
        pages = list((ROOT / "frontend" / "src" / "pages").rglob("*.tsx"))
        for page in pages:
            content = page.read_text()
            self.assertIn("import", content, f"{page.name} has no imports")


class TestDockerfiles(unittest.TestCase):
    """Validate Dockerfile syntax basics."""

    def test_backend_dockerfile(self):
        content = (ROOT / "backend" / "Dockerfile").read_text()
        self.assertIn("FROM python:", content)
        self.assertIn("COPY requirements.txt", content)
        self.assertIn("pip install", content)
        self.assertIn("CMD", content)

    def test_worker_dockerfile(self):
        content = (ROOT / "worker" / "Dockerfile").read_text()
        self.assertIn("FROM python:", content)
        self.assertIn("celery", content)

    def test_frontend_dockerfile(self):
        content = (ROOT / "frontend" / "Dockerfile").read_text()
        self.assertIn("FROM node:", content)
        self.assertIn("npm run build", content)
        self.assertIn("nginx", content)


class TestRequirements(unittest.TestCase):
    """Verify requirements.txt files have expected packages."""

    def test_backend_requirements(self):
        content = (ROOT / "backend" / "requirements.txt").read_text()
        for pkg in ["fastapi", "sqlalchemy", "pydantic", "python-jose", "passlib",
                     "celery", "qdrant-client", "structlog", "open-clip-torch"]:
            self.assertIn(pkg, content, f"Backend missing package: {pkg}")

    def test_worker_requirements(self):
        content = (ROOT / "worker" / "requirements.txt").read_text()
        for pkg in ["celery", "qdrant-client", "open-clip-torch", "sentence-transformers",
                     "torch", "Pillow", "tiktoken"]:
            self.assertIn(pkg, content, f"Worker missing package: {pkg}")


class TestEnvExample(unittest.TestCase):
    """Validate .env.example has all needed variables."""

    def test_env_vars(self):
        content = (ROOT / ".env.example").read_text()
        required = [
            "POSTGRES_PASSWORD", "QDRANT_API_KEY", "RABBITMQ_USER", "RABBITMQ_PASSWORD",
            "REDIS_PASSWORD", "SECRET_KEY", "API_PORT", "FRONTEND_PORT",
            "CLIP_MODEL_NAME", "CLIP_PRETRAINED"
        ]
        for var in required:
            self.assertIn(var, content, f"Missing env var: {var}")


class TestNginxConfig(unittest.TestCase):
    """Validate nginx proxy config."""

    def test_proxy_routes(self):
        content = (ROOT / "nginx" / "default.conf").read_text()
        self.assertIn("location /api/", content)
        self.assertIn("location /ws/", content)
        self.assertIn("location /", content)
        self.assertIn("proxy_pass", content)

    def test_websocket_support(self):
        content = (ROOT / "nginx" / "default.conf").read_text()
        self.assertIn("Upgrade", content)
        self.assertIn("upgrade", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
