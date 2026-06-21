#!/usr/bin/env python3
"""
Essence Engineering Agent — CLI entry point.

Usage:
    python main.py                        # Interactive REPL
    python main.py ask "your question"    # Single-shot query
    python main.py history                # Print stored memory
    python main.py --verbose ask "..."    # Verbose mode (shows reasoning trace)

Environment:
    Set GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY in a .env file.
"""
from __future__ import annotations

import sys

# ──────────────────────────────────────────────────────────────────────────────
# Rich UI setup (graceful fallback if not installed)
# ──────────────────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.rule import Rule
    from rich.table import Table
    from rich import print as rprint
    _RICH = True
    console = Console()
except ImportError:
    _RICH = False
    console = None  # type: ignore


def _print(text: str, **kwargs) -> None:
    if _RICH:
        console.print(text, **kwargs)
    else:
        print(text)


def _panel(title: str, content: str, style: str = "cyan") -> None:
    if _RICH:
        console.print(Panel(content, title=title, border_style=style))
    else:
        print(f"\n{'='*60}\n{title}\n{'='*60}\n{content}\n")


def _md(text: str) -> None:
    if _RICH:
        console.print(Markdown(text))
    else:
        print(text)


# ──────────────────────────────────────────────────────────────────────────────
# Banner
# ──────────────────────────────────────────────────────────────────────────────
BANNER = """
[bold cyan] ███████╗███████╗███████╗███████╗███╗   ██╗ ██████╗███████╗[/bold cyan]
[bold cyan] ██╔════╝██╔════╝██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝[/bold cyan]
[bold cyan] █████╗  ███████╗███████╗█████╗  ██╔██╗ ██║██║     █████╗  [/bold cyan]
[bold cyan] ██╔══╝  ╚════██║╚════██║██╔══╝  ██║╚██╗██║██║     ██╔══╝  [/bold cyan]
[bold cyan] ███████╗███████║███████║███████╗██║ ╚████║╚██████╗███████╗[/bold cyan]
[bold cyan] ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═══╝ ╚═════╝╚══════╝[/bold cyan]
[dim]  AI Engineering Agent — v1.0[/dim]
"""

BANNER_PLAIN = """
╔══════════════════════════════════╗
║   ESSENCE  AI Engineering Agent  ║
║            v1.0                  ║
╚══════════════════════════════════╝
"""


def print_banner() -> None:
    if _RICH:
        console.print(BANNER)
    else:
        print(BANNER_PLAIN)


# ──────────────────────────────────────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────────────────────────────────────

def display_result(result: dict, verbose: bool = False) -> None:
    response = result.get("response", "")
    reasoning = result.get("reasoning", {})
    reflection = result.get("reflection", {})
    tools_used = result.get("tools_used", [])

    # Response
    _panel("🤖  Essence", response, style="green")

    # Tools used
    if tools_used:
        _print(f"\n[dim]🔧 Tools used: {', '.join(t['tool'] for t in tools_used)}[/dim]")

    # Quality indicator
    if reflection:
        score = reflection.get("quality_score", 0)
        conf  = reflection.get("confidence", 0)
        stars = "★" * score + "☆" * (5 - score)
        _print(
            f"[dim]  Quality: {stars}  |  Confidence: {conf:.0%}  |  "
            f"Memory: {result.get('context_len', 0)} recalled[/dim]\n"
        )

    # Verbose: full reasoning trace
    if verbose:
        _print("\n[bold yellow]── Reasoning Trace ──[/bold yellow]")
        intent     = reasoning.get("intent", "?")
        complexity = reasoning.get("complexity", "?")
        plan       = reasoning.get("plan", [])
        keywords   = reasoning.get("analysis", {}).get("keywords", [])

        _print(f"  Intent:     [cyan]{intent}[/cyan]")
        _print(f"  Complexity: [yellow]{complexity}[/yellow]")
        _print(f"  Keywords:   {', '.join(keywords[:8])}")
        if plan:
            _print("  Plan:")
            for i, step in enumerate(plan, 1):
                _print(f"    {i}. {step}")

        _print("\n[bold yellow]── Reflection ──[/bold yellow]")
        _print(f"  Success:   {reflection.get('success')}")
        _print(f"  Lesson:    [italic]{reflection.get('lesson', '')}[/italic]")


def display_history(records: list) -> None:
    if not records:
        _print("[dim]No memories stored yet.[/dim]")
        return
    if _RICH:
        table = Table(title="📚 Memory History", show_lines=True, border_style="dim")
        table.add_column("#",         style="dim",   width=4)
        table.add_column("Time",      style="cyan",  width=10)
        table.add_column("Query",     style="white", no_wrap=False, max_width=50)
        table.add_column("Response",  style="green", no_wrap=False, max_width=60)
        for rec in records:
            ts = str(rec.get("timestamp", ""))[:16]
            table.add_row(
                str(rec.get("id", "")),
                ts,
                str(rec.get("query", ""))[:100],
                str(rec.get("response", ""))[:150],
            )
        console.print(table)
    else:
        for rec in records:
            print(f"\n[{rec.get('id')}] {rec.get('timestamp','')[:16]}")
            print(f"  Q: {rec.get('query','')[:80]}")
            print(f"  A: {rec.get('response','')[:100]}")


# ──────────────────────────────────────────────────────────────────────────────
# Modes
# ──────────────────────────────────────────────────────────────────────────────

def run_single_query(query: str, verbose: bool) -> None:
    from core.orchestrator import Orchestrator
    system = Orchestrator()
    _print(f"[dim]Processing: {query!r}[/dim]")
    result = system.run(query)
    display_result(result, verbose=verbose)


def run_repl(verbose: bool) -> None:
    from core.orchestrator import Orchestrator
    print_banner()
    system = Orchestrator()
    mem_count = system.memory_count()

    _print(f"[dim]  Provider: [bold]{system.agent.provider}[/bold]  |  "
           f"Model: [bold]{system.agent.model}[/bold]  |  "
           f"Memories: [bold]{mem_count}[/bold][/dim]")
    _print("[dim]  Type [bold]exit[/bold] or [bold]quit[/bold] to leave. "
           "[bold]/history[/bold] to view memory. [bold]/verbose[/bold] to toggle trace.[/dim]\n")

    while True:
        try:
            if _RICH:
                query = Prompt.ask("[bold cyan]You[/bold cyan]").strip()
            else:
                query = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            _print("\n[dim]Goodbye.[/dim]")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit", "bye"):
            _print("[dim]Goodbye.[/dim]")
            break
        if query == "/history":
            display_history(system.history())
            continue
        if query == "/verbose":
            verbose = not verbose
            _print(f"[dim]Verbose mode: {'ON' if verbose else 'OFF'}[/dim]")
            continue
        if query.startswith("/help"):
            _print("[dim]Commands: /history, /verbose, exit[/dim]")
            continue

        result = system.run(query)
        display_result(result, verbose=verbose)


def show_history() -> None:
    from core.orchestrator import Orchestrator
    system = Orchestrator()
    records = system.history()
    display_history(records)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    # Parse --verbose flag
    verbose = "--verbose" in args or "-v" in args
    args = [a for a in args if a not in ("--verbose", "-v")]

    if not args:
        run_repl(verbose=verbose)
        return

    command = args[0].lower()

    if command == "ask":
        if len(args) < 2:
            _print("[red]Usage: python main.py ask \"your question\"[/red]")
            sys.exit(1)
        run_single_query(args[1], verbose=verbose)

    elif command == "history":
        show_history()

    else:
        _print(f"[red]Unknown command: {command!r}[/red]")
        _print("Usage:")
        _print("  python main.py                  — interactive REPL")
        _print("  python main.py ask \"question\"   — single query")
        _print("  python main.py history          — view memory")
        _print("  --verbose / -v                  — show reasoning trace")
        sys.exit(1)


if __name__ == "__main__":
    main()