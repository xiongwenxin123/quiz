"""Android entry point for the bundled loopback HTTP server."""

from __future__ import annotations

import os
from pathlib import Path


def configure(app_files_dir: str) -> None:
    """Point mutable application state at Android's private files directory."""
    files_dir = Path(app_files_dir)
    files_dir.mkdir(parents=True, exist_ok=True)
    provider_path = files_dir / "provider-settings.json"
    os.environ["QUIZ_PROVIDER_CONFIG_PATH"] = str(provider_path)

    # The package initializer imports providers before this module can run.
    from . import providers

    providers.DEFAULT_PROVIDER_PATH = provider_path


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the API until Android terminates the application process."""
    import uvicorn

    from .api import create_app

    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
