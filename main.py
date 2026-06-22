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

import argparse
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


def _table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    if not rows:
        _print("[dim]No records found.[/dim]")
        return
    if _RICH:
        table = Table(title=title, show_lines=False, border_style="dim")
        for col in columns:
            table.add_column(col, no_wrap=False)
        for row in rows:
            table.add_row(*[str(cell) for cell in row])
        console.print(table)
    else:
        print(title)
        print(" | ".join(columns))
        print("-" * 80)
        for row in rows:
            print(" | ".join(str(cell) for cell in row))


def display_backlog(items: list) -> None:
    rows = [
        [
            f"{item.id}",
            item.title,
            item.type,
            item.priority,
            item.status,
            str(item.sprint_id or "-"),
            item.tags or "-",
        ]
        for item in items
    ]
    _table("Backlog", ["ID", "Title", "Type", "Priority", "Status", "Sprint", "Tags"], rows)


def display_sprints(sprints: list) -> None:
    rows = [
        [
            f"{sprint.id}",
            sprint.name,
            sprint.status,
            sprint.goal or "-",
            sprint.start_date[:10] if sprint.start_date else "-",
            sprint.end_date[:10] if sprint.end_date else "-",
            str(sprint.velocity),
        ]
        for sprint in sprints
    ]
    _table("Sprints", ["ID", "Name", "Status", "Goal", "Start", "End", "Velocity"], rows)


def display_issues(issues: list) -> None:
    rows = [
        [
            f"{issue.id}",
            issue.title,
            issue.type,
            issue.severity,
            issue.status,
            str(issue.backlog_item_id or "-"),
        ]
        for issue in issues
    ]
    _table("Issues", ["ID", "Title", "Type", "Severity", "Status", "Backlog"], rows)


def display_review(result: dict) -> None:
    if result.get("error"):
        _print(f"[red]{result['error']}[/red]")
        return
    content = "\n\n".join([
        "## Summary\n" + (result.get("summary") or ""),
        "## Concerns\n" + (result.get("concerns") or "None identified."),
        "## Suggestions\n" + (result.get("suggestions") or "None."),
        "## Severity\n" + (result.get("severity") or "MEDIUM"),
        "## Verdict\n" + (result.get("verdict") or ""),
    ])
    _md(content)


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


def _load_system():
    from core.orchestrator import Orchestrator
    return Orchestrator()


def handle_backlog(args: argparse.Namespace) -> None:
    system = _load_system()
    action = args.backlog_command

    if action == "add":
        item = system.backlog.add(
            title=args.title,
            type=args.type,
            priority=args.priority,
            description=args.description or "",
            tags=args.tags or "",
        )
        _print(f"Added backlog item: {item.short_repr()}")
    elif action == "list":
        display_backlog(system.backlog.list(
            status=args.status,
            type=args.type,
            priority=args.priority,
            sprint_id=args.sprint,
            limit=args.limit,
        ))
    elif action == "search":
        display_backlog(system.backlog.search(args.keyword))
    elif action == "status":
        ok = system.backlog.update_status(args.item_id, args.status)
        _print("Updated backlog status." if ok else "[red]Invalid backlog status.[/red]")
        if not ok:
            sys.exit(1)
    elif action == "priority":
        ok = system.backlog.update_priority(args.item_id, args.priority)
        _print("Updated backlog priority." if ok else "[red]Invalid backlog priority.[/red]")
        if not ok:
            sys.exit(1)
    elif action == "assign":
        if not system.backlog.get(args.item_id):
            _print(f"[red]Backlog item not found: {args.item_id}[/red]")
            sys.exit(1)
        if not system.sprints.get(args.sprint_id):
            _print(f"[red]Sprint not found: {args.sprint_id}[/red]")
            sys.exit(1)
        system.backlog.assign_sprint(args.item_id, args.sprint_id)
        _print(f"Assigned backlog item {args.item_id} to sprint {args.sprint_id}.")


def handle_sprint(args: argparse.Namespace) -> None:
    system = _load_system()
    action = args.sprint_command

    if action == "create":
        sprint = system.sprints.create(args.name, goal=args.goal or "", end_date=args.end_date or "")
        display_sprints([sprint])
    elif action == "start":
        ok = system.sprints.start(args.sprint_id)
        _print("Sprint started." if ok else "[red]Another sprint is already active.[/red]")
        if not ok:
            sys.exit(1)
    elif action == "close":
        sprint = system.sprints.close(args.sprint_id)
        if not sprint:
            _print(f"[red]Sprint not found: {args.sprint_id}[/red]")
            sys.exit(1)
        display_sprints([sprint])
    elif action == "list":
        display_sprints(system.sprints.list(status=args.status, limit=args.limit))
    elif action == "report":
        _md(system.reporter.sprint_report(args.sprint_id))


def handle_issue(args: argparse.Namespace) -> None:
    system = _load_system()
    action = args.issue_command

    if action == "report":
        issue = system.issues.report(
            title=args.title,
            type=args.type,
            severity=args.severity,
            description=args.description or "",
            backlog_item_id=args.backlog_item,
        )
        _print(f"Reported issue: {issue.short_repr()}")
    elif action == "list":
        display_issues(system.issues.list(
            status=args.status,
            severity=args.severity,
            type=args.type,
            limit=args.limit,
        ))
    elif action == "resolve":
        system.issues.resolve(args.issue_id, notes=args.notes or "")
        _print(f"Resolved issue {args.issue_id}.")
    elif action == "status":
        ok = system.issues.update_status(args.issue_id, args.status)
        _print("Updated issue status." if ok else "[red]Invalid issue status.[/red]")
        if not ok:
            sys.exit(1)
    elif action == "note":
        system.issues.add_note(args.issue_id, args.note)
        _print(f"Added note to issue {args.issue_id}.")


def handle_report(args: argparse.Namespace) -> None:
    system = _load_system()
    if args.report_command == "project":
        _md(system.reporter.project_summary())
    elif args.report_command == "standup":
        _md(system.reporter.daily_standup())
    elif args.report_command == "sprint":
        _md(system.reporter.sprint_report(args.sprint_id))


def handle_review(args: argparse.Namespace) -> None:
    system = _load_system()
    if args.review_command == "latest":
        display_review(system.reviewer.review_latest_git(args.commits))
    elif args.review_command == "file":
        display_review(system.reviewer.review_file(args.path))


def handle_changelog(args: argparse.Namespace) -> None:
    system = _load_system()
    content = system.changelog.generate(
        version=args.version,
        since_sprint_id=args.sprint_id,
        output_path=args.output,
    )
    _md(content)


def build_parser() -> argparse.ArgumentParser:
    from sdlc.models import (
        ISSUE_STATUSES,
        ISSUE_TYPES,
        ITEM_STATUSES,
        ITEM_TYPES,
        PRIORITIES,
        SEVERITIES,
        SPRINT_STATUSES,
    )

    parser = argparse.ArgumentParser(prog="python3 main.py", description="Forge SDLC Manager for Essence")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show reasoning trace for ask/REPL")
    sub = parser.add_subparsers(dest="command")

    ask = sub.add_parser("ask", help="Run a single agent query")
    ask.add_argument("query", nargs="+")

    sub.add_parser("history", help="Show stored memory")

    backlog = sub.add_parser("backlog", help="Manage backlog items")
    backlog_sub = backlog.add_subparsers(dest="backlog_command", required=True)
    backlog_add = backlog_sub.add_parser("add")
    backlog_add.add_argument("title")
    backlog_add.add_argument("--type", choices=ITEM_TYPES, default="task")
    backlog_add.add_argument("--priority", choices=PRIORITIES, default="medium")
    backlog_add.add_argument("--description", default="")
    backlog_add.add_argument("--tags", default="")
    backlog_list = backlog_sub.add_parser("list")
    backlog_list.add_argument("--status", choices=ITEM_STATUSES)
    backlog_list.add_argument("--type", choices=ITEM_TYPES)
    backlog_list.add_argument("--priority", choices=PRIORITIES)
    backlog_list.add_argument("--sprint", type=int)
    backlog_list.add_argument("--limit", type=int, default=50)
    backlog_search = backlog_sub.add_parser("search")
    backlog_search.add_argument("keyword")
    backlog_status = backlog_sub.add_parser("status")
    backlog_status.add_argument("item_id", type=int)
    backlog_status.add_argument("status", choices=ITEM_STATUSES)
    backlog_priority = backlog_sub.add_parser("priority")
    backlog_priority.add_argument("item_id", type=int)
    backlog_priority.add_argument("priority", choices=PRIORITIES)
    backlog_assign = backlog_sub.add_parser("assign")
    backlog_assign.add_argument("item_id", type=int)
    backlog_assign.add_argument("sprint_id", type=int)

    sprint = sub.add_parser("sprint", help="Manage sprints")
    sprint_sub = sprint.add_subparsers(dest="sprint_command", required=True)
    sprint_create = sprint_sub.add_parser("create")
    sprint_create.add_argument("name")
    sprint_create.add_argument("--goal", default="")
    sprint_create.add_argument("--end-date", default="")
    sprint_start = sprint_sub.add_parser("start")
    sprint_start.add_argument("sprint_id", type=int)
    sprint_close = sprint_sub.add_parser("close")
    sprint_close.add_argument("sprint_id", type=int)
    sprint_list = sprint_sub.add_parser("list")
    sprint_list.add_argument("--status", choices=SPRINT_STATUSES)
    sprint_list.add_argument("--limit", type=int, default=20)
    sprint_report = sprint_sub.add_parser("report")
    sprint_report.add_argument("sprint_id", type=int, nargs="?")

    issue = sub.add_parser("issue", help="Track bugs, blockers, risks, and questions")
    issue_sub = issue.add_subparsers(dest="issue_command", required=True)
    issue_report = issue_sub.add_parser("report")
    issue_report.add_argument("title")
    issue_report.add_argument("--type", choices=ISSUE_TYPES, default="bug")
    issue_report.add_argument("--severity", choices=SEVERITIES, default="medium")
    issue_report.add_argument("--description", default="")
    issue_report.add_argument("--backlog-item", type=int)
    issue_list = issue_sub.add_parser("list")
    issue_list.add_argument("--status", choices=ISSUE_STATUSES)
    issue_list.add_argument("--severity", choices=SEVERITIES)
    issue_list.add_argument("--type", choices=ISSUE_TYPES)
    issue_list.add_argument("--limit", type=int, default=50)
    issue_resolve = issue_sub.add_parser("resolve")
    issue_resolve.add_argument("issue_id", type=int)
    issue_resolve.add_argument("--notes", default="")
    issue_status = issue_sub.add_parser("status")
    issue_status.add_argument("issue_id", type=int)
    issue_status.add_argument("status", choices=ISSUE_STATUSES)
    issue_note = issue_sub.add_parser("note")
    issue_note.add_argument("issue_id", type=int)
    issue_note.add_argument("note")

    report = sub.add_parser("report", help="Generate project reports")
    report_sub = report.add_subparsers(dest="report_command", required=True)
    report_sub.add_parser("project")
    report_sub.add_parser("standup")
    report_sprint = report_sub.add_parser("sprint")
    report_sprint.add_argument("sprint_id", type=int, nargs="?")

    review = sub.add_parser("review", help="Review code using the configured LLM")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    review_latest = review_sub.add_parser("latest")
    review_latest.add_argument("--commits", type=int, default=1)
    review_file = review_sub.add_parser("file")
    review_file.add_argument("path")

    changelog = sub.add_parser("changelog", help="Generate changelog text")
    changelog_sub = changelog.add_subparsers(dest="changelog_command", required=True)
    changelog_generate = changelog_sub.add_parser("generate")
    changelog_generate.add_argument("--version", default="Unreleased")
    changelog_generate.add_argument("--sprint-id", type=int)
    changelog_generate.add_argument("--output")

    return parser


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if not args:
        run_repl(verbose=False)
        return

    parser = build_parser()
    parsed = parser.parse_args(args)

    if parsed.command == "ask":
        run_single_query(" ".join(parsed.query), verbose=parsed.verbose)
    elif parsed.command == "history":
        show_history()
    elif parsed.command == "backlog":
        handle_backlog(parsed)
    elif parsed.command == "sprint":
        handle_sprint(parsed)
    elif parsed.command == "issue":
        handle_issue(parsed)
    elif parsed.command == "report":
        handle_report(parsed)
    elif parsed.command == "review":
        handle_review(parsed)
    elif parsed.command == "changelog":
        handle_changelog(parsed)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
