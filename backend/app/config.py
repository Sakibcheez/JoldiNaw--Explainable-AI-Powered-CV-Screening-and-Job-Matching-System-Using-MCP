from pathlib import Path
from urllib.parse import urlsplit
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "sqlite:///./joldinaw.db"
    redis_url: str = "redis://localhost:6379/0"
    task_mode: str = "rq"
    storage_dir: Path = Path("storage")
    jwt_secret: str = ""
    demo_password: str = ""
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_client_id: str = ""
    oidc_redirect_uri: str = ""
    oidc_scopes: str = "openid profile email read write"
    cors_origins: str = "http://localhost:5173"
    embedding_path: str = ""
    embedding_revision: str = ""
    mcp_hosts: str = "localhost,127.0.0.1,localhost:*,127.0.0.1:*"

    def validate_runtime(self):
        if self.embedding_path and not self.embedding_revision:
            raise RuntimeError("Configured embeddings require an explicit model revision")
        if self.app_env == "production":
            if not all(
                [
                    self.oidc_issuer,
                    self.oidc_audience,
                    self.oidc_jwks_url,
                    self.oidc_client_id,
                    self.oidc_redirect_uri,
                ]
            ):
                raise RuntimeError("Production requires OIDC issuer, audience, JWKS URL, client ID and redirect URI")
            if any(
                urlsplit(value).scheme != "https" or not urlsplit(value).netloc
                for value in (self.oidc_issuer, self.oidc_jwks_url, self.oidc_redirect_uri)
            ):
                raise RuntimeError("Production OIDC issuer, JWKS URL and redirect URI must use HTTPS")
            if not self.database_url.startswith("postgresql") or self.task_mode != "rq":
                raise RuntimeError("Production requires PostgreSQL and RQ")
        elif len(self.jwt_secret) < 32:
            raise RuntimeError("Set JWT_SECRET to at least 32 random characters")


settings = Settings()
