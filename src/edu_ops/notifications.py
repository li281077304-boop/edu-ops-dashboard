"""Optional local failure notifications for unattended macOS runs."""

from __future__ import annotations

import platform
import subprocess


def notify_local_failure(message: str) -> None:
    """Show a best-effort macOS notification without including credentials."""
    if platform.system() != "Darwin":
        return
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    script = f'display notification "{safe_message}" with title "edu-ops-dashboard"'
    subprocess.run(
        ["osascript", "-e", script],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
