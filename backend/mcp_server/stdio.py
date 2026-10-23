"""Local, development-only stdio transport with the explicitly configured demo identity."""
from app.auth import demo_token, verify_token
from app.config import settings
from mcp_server.server import current_identity, mcp


def main():
    if settings.app_env != "development" or not settings.demo_password:
        raise RuntimeError("Local stdio demo transport is disabled outside development")
    who = verify_token(demo_token(settings.demo_password))
    principal = current_identity.set(who)
    try:
        mcp.run("stdio")
    finally:
        current_identity.reset(principal)


if __name__ == "__main__":
    main()
