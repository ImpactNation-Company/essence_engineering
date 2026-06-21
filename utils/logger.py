"""
Enhanced structured logger with timestamps and optional Rich integration.
Falls back gracefully if Rich is not installed.
"""
import sys
from datetime import datetime

try:
    from rich.console import Console
    from rich.text import Text
    _console = Console(stderr=True)
    _RICH = True
except ImportError:
    _RICH = False

# Colour palette per tag (Rich markup, only used when Rich is available)
_TAG_STYLES = {
    "ORCH":    "bold cyan",
    "REASON":  "bold blue",
    "AGENT":   "bold green",
    "MEM":     "bold yellow",
    "REFLECT": "bold magenta",
    "TOOL":    "bold orange3",
    "ERROR":   "bold red",
    "INFO":    "dim white",
}


def log(tag: str, message: str) -> None:
    """Emit a timestamped, colour-coded log line."""
    ts = datetime.now().strftime("%H:%M:%S")
    if _RICH:
        style = _TAG_STYLES.get(tag.upper(), "white")
        label = Text(f"[{tag}]", style=style)
        _console.print(f"[dim]{ts}[/dim] ", label, message)
    else:
        print(f"{ts} [{tag}] {message}", file=sys.stderr)
