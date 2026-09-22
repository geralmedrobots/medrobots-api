from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_runs_as_non_root_without_reload() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text()
    assert "USER api" in content
    assert "--reload" not in content
    assert "HEALTHCHECK" in content
    assert "AS builder" in content
    # Migrations must not run as part of the container's default command in
    # production images; they are a separate, explicit step (see docker-compose
    # "migrate" service and README "Startup e migrations").
    assert "alembic upgrade head" not in content


def test_docker_compose_runs_migrations_as_separate_step() -> None:
    content = (REPO_ROOT / "docker-compose.yml").read_text()
    assert "migrate:" in content
    assert "alembic" in content
    assert "service_completed_successfully" in content
    assert "ENVIRONMENT: production" not in content


def test_dockerignore_excludes_dev_only_files() -> None:
    content = (REPO_ROOT / ".dockerignore").read_text()
    for entry in (".venv", ".env", "tests", ".git"):
        assert entry in content
