"""Vega CLI — Command-line interface for the Vega Agent.

Commands:
    vega init          Interactive setup, creates ``~/.vega/`` directory
    vega ask           Ask the agent a question
    vega shell         Interactive REPL
    vega status        Show system status, config, version
    vega audit         Show recent audit trail entries
    vega privacy       Show privacy status, data locations, and configuration
    vega encrypt       Optional local encryption setup
    vega migrate       Import from an Obsidian vault
    vega --version     Show version
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vega import __version__
from vega.config import DEFAULT_CONFIG, Config
from vega.model import ModelRouter, ModelRouterError
from vega.privacy import (
    count_entries,
    decrypt_file,
    encrypt_file,
    generate_key,
    list_log_files,
    log_audit,
    read_recent,
)
from vega.privacy.audit import _ensure_audit_dir as _audit_dir

# ---------------------------------------------------------------------------
# Rich console
# ---------------------------------------------------------------------------

console = Console()

# ---------------------------------------------------------------------------
# Top-level group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version=__version__, prog_name="vega")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Vega — Your Personal AI. Installed. Private."""
    ctx.ensure_object(dict)
    # Try to load config; store None if not yet initialised
    try:
        ctx.obj["config"] = Config()
    except FileNotFoundError:
        ctx.obj["config"] = None


# ═════════════════════════════════════════════════════════════════════════
# vega init
# ═════════════════════════════════════════════════════════════════════════


@main.command()
@click.option("--auto", is_flag=True, help="Skip prompts, use defaults.")
@click.pass_context
def init(ctx: click.Context, auto: bool) -> None:
    """Initialise Vega — creates ``~/.vega/``, config, and API key setup.

    If ``--auto`` is passed, uses defaults and skips all prompts.
    """
    vega_dir = Path.home() / ".vega"
    config_path = vega_dir / "config.yaml"

    if config_path.exists():
        console.print("[yellow]Vega is already initialised.[/yellow]")
        console.print(f"  Config: {config_path}")
        if not auto:
            proceed = click.confirm("Re-initialise and overwrite?", default=False)
            if not proceed:
                console.print("[dim]Aborted.[/dim]")
                return

    # ── Create directory structure ──────────────────────────────────────
    vega_dir.mkdir(parents=True, exist_ok=True)
    (vega_dir / "data").mkdir(parents=True, exist_ok=True)
    (vega_dir / "audit").mkdir(parents=True, exist_ok=True)
    (vega_dir / "chromadb").mkdir(parents=True, exist_ok=True)
    console.print("[green]✓ Created ~/.vega/ directory structure[/green]")

    # ── Gather config values ────────────────────────────────────────────
    if auto:
        cfg_data = _deep_copy(DEFAULT_CONFIG)
        api_key = ""
    else:
        import questionary

        cfg_data = _deep_copy(DEFAULT_CONFIG)
        console.print(Panel.fit(
            "[bold]Vega Initialisation[/bold]\nConfigure your personal AI agent.",
            title="vega init",
        ))

        # Model provider (arrow-key selection)
        provider = questionary.select(
            "Select your LLM provider:",
            choices=[
                questionary.Choice(
                    "OpenRouter — cloud API (recommended for beginners)", "openrouter",
                ),
                questionary.Choice(
                    "OpenAI — direct API via OpenAI", "openai",
                ),
                questionary.Choice(
                    "Ollama — local models, no API key needed", "ollama",
                ),
            ],
            default="openrouter",
            use_arrow_keys=True,
        ).ask()
        if not provider:
            provider = "openrouter"
        cfg_data["model"]["provider"] = provider.strip()

        # API key (skip for Ollama)
        api_key = ""
        if provider != "ollama":
            console.print("\n[bold]API Key[/bold]")
            api_key = click.prompt(
                "  Provider API key",
                default="",
                hide_input=True,
                show_default=False,
            )

        # Model name
        if provider == "ollama":
            # Ollama model selection flow
            from vega.model.ollama_helper import (
                check_ollama_installed,
                check_ollama_running,
                install_ollama,
                list_local_models,
                pick_model_interactive,
                pull_model,
                start_ollama,
            )

            # Check installation
            if not check_ollama_installed():
                console.print("\n[yellow]Ollama is not installed on this system.[/yellow]")
                if questionary.confirm(
                    "Install Ollama now? (requires curl + sudo)",
                    default=True,
                ).ask():
                    install_ollama()
                else:
                    console.print("[dim]You can install it later: curl -fsSL https://ollama.com/install.sh | sh[/dim]")

            # Check running
            if not check_ollama_running():
                console.print("[yellow]Ollama server is not running.[/yellow]")
                if questionary.confirm("Start Ollama now?", default=True).ask():
                    start_ollama()
                    import time
                    # Poll until running (10 seconds max)
                    for _ in range(10):
                        time.sleep(1)
                        if check_ollama_running():
                            break

            # List local models and pick
            local = list_local_models()
            chosen = pick_model_interactive(local_models=local if local else None)

            if chosen:
                cfg_data["model"]["name"] = chosen
                # If model not local, offer to pull
                if not local or chosen not in local:
                    if questionary.confirm(
                        f"Pull {chosen} now? (requires internet)", default=True,
                    ).ask():
                        pull_model(chosen)
            else:
                cfg_data["model"]["name"] = "llama3.2:3b"
        else:
            # Cloud provider — free-text model name
            model_name = click.prompt(
                "  Model name",
                default=cfg_data["model"]["name"],
            )
            cfg_data["model"]["name"] = model_name.strip()

        # Privacy toggles
        console.print("\n[bold]Privacy Settings[/bold]")
        if click.confirm("  Disable telemetry?", default=True):
            cfg_data["privacy"]["telemetry"] = False
        if click.confirm("  Disable cloud sync?", default=True):
            cfg_data["privacy"]["cloud_sync"] = False
        if click.confirm("  Use local models only?", default=False):
            cfg_data["privacy"]["local_models_only"] = True

        # Features
        console.print("\n[bold]Features[/bold]")
        if not click.confirm("  Enable memory (vector recall)?", default=True):
            cfg_data["features"]["memory"] = False
        if not click.confirm("  Enable context tree (knowledge graph)?", default=True):
            cfg_data["features"]["context_tree"] = False

        console.print("")

    # ── Write config ────────────────────────────────────────────────────
    import yaml
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg_data, f, default_flow_style=False, sort_keys=False)
    console.print(f"[green]✓ Config written to {config_path}[/green]")

    # ── Write API key if provided ───────────────────────────────────────
    if api_key:
        key_path = vega_dir / ".api_key"
        with open(key_path, "w", encoding="utf-8") as f:
            f.write(api_key.strip() + "\n")
        key_path.chmod(0o600)
        console.print("[green]✓ API key saved to ~/.vega/.api_key (mode 600)[/green]")

    # ── Test setup ──────────────────────────────────────────────────────
    if not auto and cfg_data["model"]["provider"] != "ollama":
        if click.confirm("\nTest the setup with a quick API call?", default=True):
            _test_setup(api_key or _read_api_key(), cfg_data["model"])

    console.print("\n[bold green]Vega is ready![/bold green]")
    console.print("  Try:  vega ask \"What can you do?\"")
    console.print("  Try:  vega shell")
    console.print("  Try:  vega status\n")


def _test_setup(api_key: str, model_cfg: dict) -> None:
    """Make a quick API call to verify connectivity."""
    if not api_key:
        console.print("[yellow]Skipping test — no API key configured.[/yellow]")
        return
    console.print("\n[bold]Testing API connection ...[/bold]")
    try:
        import httpx
        provider = model_cfg.get("provider", "openrouter")
        if provider == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        else:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

        payload = {
            "model": model_cfg.get("name", "deepseek/deepseek-v4-flash"),
            "messages": [{"role": "user", "content": "Say 'Vega setup OK' and nothing else."}],
            "max_tokens": 20,
        }

        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]["content"]
            console.print(f"[green]✓ API response: {msg.strip()}[/green]")
    except Exception as exc:
        console.print(f"[yellow]⚠ Test failed: {exc}[/yellow]")
        console.print("  You can still use Vega — check your API key and network.")


def _read_api_key() -> str:
    key_path = Path.home() / ".vega" / ".api_key"
    if key_path.exists():
        return key_path.read_text().strip()
    return ""


def _deep_copy(d: dict) -> dict:
    import copy
    return copy.deepcopy(d)


# ═════════════════════════════════════════════════════════════════════════
# vega ask
# ═════════════════════════════════════════════════════════════════════════


@main.command()
@click.argument("question", nargs=-1, required=True)
@click.option("--model", "-m", default=None, help="Override model name.")
@click.option("--provider", "-p", default=None, help="Override provider.")
@click.pass_context
def ask(ctx: click.Context, question: tuple[str, ...], model: Optional[str], provider: Optional[str]) -> None:
    """Ask the Vega agent a question.

    Context-aware: searches the context tree and memory for relevant
    information before calling the LLM, and stores the Q&A in episodic
    memory afterwards.
    """
    full_question = " ".join(question)
    cfg: Optional[Config] = ctx.obj.get("config")

    model_name = model or (cfg.get("model", "name") if cfg else "deepseek/deepseek-v4-flash")
    provider_name = provider or (cfg.get("model", "provider") if cfg else "openrouter")

    # API key check
    if not _read_api_key():
        console.print("[red]No API key found. Run [bold]vega init[/bold] first.[/red]")
        sys.exit(1)

    # Route through gateway for audit + scope enforcement
    try:
        from vega.gateway import route_llm_call

        gw_result = route_llm_call(
            prompt=full_question,
            target=f"{provider_name}-chat",
            model=model_name,
            why="User asked a question via CLI",
        )
        if not gw_result.ok:
            console.print(f"[red]Blocked by privacy gateway: {gw_result.reason}[/red]")
            sys.exit(1)
    except Exception:
        pass  # gateway audit is best-effort

    console.print(f"[dim]Asking {model_name} ...[/dim]")

    # ── Context-aware search ──────────────────────────────────────────────
    context_entries: list[dict] = []
    memory_enabled = cfg.get("features", "memory", True) if cfg else True
    context_tree_enabled = cfg.get("features", "context_tree", True) if cfg else True

    db = None
    mem = None

    if context_tree_enabled:
        try:
            from vega.context_tree.db import ContextTreeDB

            db_path = cfg.context_tree_db_path if cfg else None
            db = ContextTreeDB(db_path=str(db_path) if db_path else None)
            db.initialize()
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not initialise context tree: {exc}[/yellow]")
            db = None

    if memory_enabled:
        try:
            from vega.memory.vector import MemoryStore

            chromadb_dir = cfg.chromadb_dir if cfg else None
            mem = MemoryStore(persist_dir=str(chromadb_dir) if chromadb_dir else None)
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not initialise memory: {exc}[/yellow]")
            mem = None

    # Semantic search across context tree (with ChromaDB fallback)
    if db is not None:
        try:
            context_entries = db.semantic_search(full_question, limit=10, memory_store=mem)
        except Exception as exc:
            console.print(f"[yellow]Warning: Context search failed: {exc}[/yellow]")

    # Also search episodic memory for similar past interactions
    episodic_context: list[dict] = []
    if mem is not None:
        try:
            episodic_context = mem.search(full_question, n_results=5, collection="vega_episodic")
        except Exception as exc:
            console.print(f"[dim]Episodic search unavailable: {exc}[/dim]")

    # ── Build enriched prompt ─────────────────────────────────────────────
    messages: list[dict] = []

    if context_entries:
        context_lines = []
        for entry in context_entries[:5]:  # top 5 to stay within context window
            snippet = entry.get("content", "")[:200] if entry.get("content") else ""
            title = entry.get("title", "Untitled")
            context_lines.append(f"- {title}: {snippet}")
        context_block = "\n".join(context_lines)
        messages.append(
            {
                "role": "system",
                "content": f"Context from your knowledge base:\n{context_block}",
            }
        )

    if episodic_context:
        episodic_lines = []
        for ep in episodic_context[:3]:
            doc = ep.get("document") or ""
            if doc:
                episodic_lines.append(f"- {doc[:200]}")
        if episodic_lines:
            ep_block = "\n".join(episodic_lines)
            if messages:
                messages[0]["content"] += f"\n\nRelated past interactions:\n{ep_block}"
            else:
                messages.append(
                    {
                        "role": "system",
                        "content": f"Related past interactions:\n{ep_block}",
                    }
                )

    messages.append({"role": "user", "content": full_question})

    # ── Call LLM ──────────────────────────────────────────────────────────
    response_content = ""
    try:
        # Build router config — use overrides if provided, otherwise from config
        router_cfg = cfg.data if cfg else {}
        if model or provider:
            router_cfg = {
                "model": {
                    "provider": provider_name,
                    "name": model_name,
                    "temperature": cfg.get("model", "temperature", 0.7) if cfg else 0.7,
                    "max_tokens": cfg.get("model", "max_tokens", 4096) if cfg else 4096,
                }
            }

        router = ModelRouter(config=router_cfg)
        result = router.complete(messages=messages)
        response_content = result["content"]
        console.print(response_content)
    except ModelRouterError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[red]Unexpected error: {exc}[/red]")
        sys.exit(1)

    # ── Post-response: store in episodic memory and touch nodes ──────────
    if response_content and mem is not None:
        try:
            mem.store(
                text=f"Q: {full_question}\nA: {response_content}",
                metadata={"source": "vega-ask", "timestamp": datetime.now(timezone.utc).isoformat()},
                collection="vega_episodic",
            )
        except Exception as exc:
            console.print(f"[dim]Could not store to episodic memory: {exc}[/dim]")

    if response_content and db is not None:
        for entry in context_entries:
            if entry.get("source") == "context_tree" and entry.get("node_id"):
                try:
                    db.touch_node(entry["node_id"])
                except Exception:
                    pass


# ═════════════════════════════════════════════════════════════════════════
# vega shell
# ═════════════════════════════════════════════════════════════════════════


@main.command()
@click.option("--model", "-m", default=None, help="Override model name.")
@click.pass_context
def shell(ctx: click.Context, model: Optional[str]) -> None:
    """Start an interactive REPL with the Vega agent.

    Type ``/exit`` or ``Ctrl+C`` to quit.  Type ``/help`` for commands.
    """
    cfg: Optional[Config] = ctx.obj.get("config")
    model_name = model or (cfg.get("model", "name") if cfg else "deepseek/deepseek-v4-flash")
    provider_name = cfg.get("model", "provider") if cfg else "openrouter"

    # Check API key exists
    if not _read_api_key():
        console.print("[red]No API key found. Run [bold]vega init[/bold] first.[/red]")
        sys.exit(1)

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are Vega, a personal AI agent. You are helpful, knowledgeable, "
                "and direct. Keep responses concise unless the user asks for detail. "
                "You run as a local CLI tool."
            ),
        }
    ]

    console.print(Panel.fit(
        "[bold]Vega Shell[/bold]\n"
        "Type your messages.  Commands: [italic]/exit[/italic] to quit, "
        "[italic]/help[/italic] for help, [italic]/clear[/italic] to reset context.",
        title=f"vega shell ({model_name})",
        border_style="green",
    ))

    from vega.gateway import route_llm_call

    while True:
        try:
            user_input = click.prompt("\n[bold green]You[/bold green]", prompt_suffix=" > ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        cmd = user_input.strip().lower()

        if cmd in ("/exit", "/quit", "/q"):
            console.print("[yellow]Goodbye![/yellow]")
            break
        if cmd in ("/help", "/h"):
            _print_shell_help()
            continue
        if cmd in ("/clear", "/reset"):
            messages.clear()
            messages.append({
                "role": "system",
                "content": (
                    "You are Vega, a personal AI agent. You are helpful, knowledgeable, "
                    "and direct. Keep responses concise."
                ),
            })
            console.print("[dim]Context cleared.[/dim]")
            continue
        if not user_input.strip():
            continue

        # Route through gateway for audit + scope enforcement
        try:
            gw_result = route_llm_call(
                prompt=user_input,
                target=f"{provider_name}-chat",
                model=model_name,
                why="User message in interactive shell",
            )
            if not gw_result.ok:
                console.print(f"[red]Blocked by privacy gateway: {gw_result.reason}[/red]")
                continue
        except Exception:
            pass  # gateway audit is best-effort

        messages.append({"role": "user", "content": user_input})

        try:
            router = ModelRouter(config=cfg.data if cfg else {})
            result = router.complete(
                messages=messages,
            )
            reply = result["content"]
            console.print("\n[bold blue]Vega[/bold blue]")
            console.print(reply)
            messages.append({"role": "assistant", "content": reply})
        except ModelRouterError as exc:
            console.print(f"[red]Error: {exc}[/red]")
        except Exception as exc:
            console.print(f"[red]Unexpected error: {exc}[/red]")


def _print_shell_help() -> None:
    console.print(Panel.fit(
        "[bold]Shell Commands[/bold]\n\n"
        "  [italic]/exit[/italic]   Exit the shell\n"
        "  [italic]/quit[/italic]   Exit the shell\n"
        "  [italic]/clear[/italic]  Reset conversation context\n"
        "  [italic]/help[/italic]   Show this help\n"
        "  [italic]/stats[/italic]  Show current model and token info (not yet implemented)\n\n"
        "Everything else is sent to the LLM as a message.",
        title="Help",
        border_style="blue",
    ))


# ═════════════════════════════════════════════════════════════════════════
# vega status
# ═════════════════════════════════════════════════════════════════════════


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show system status, configuration, and version information."""
    cfg: Optional[Config] = ctx.obj.get("config")

    table = Table(title="Vega Status", box=box.ROUNDED)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Version", __version__)
    table.add_row("Python", sys.version.split()[0])
    table.add_row("Platform", sys.platform)

    if cfg:
        table.add_row("Config", str(cfg.path))
        model_section = cfg.model
        table.add_row("Model Provider", model_section.get("provider", "—"))
        table.add_row("Model Name", model_section.get("name", "—"))
        table.add_row("Temperature", str(model_section.get("temperature", "—")))
        table.add_row("Max Tokens", str(model_section.get("max_tokens", "—")))

        # Privacy
        priv = cfg.privacy
        table.add_row("Telemetry", "Disabled" if not priv.get("telemetry") else "Enabled")
        table.add_row("Cloud Sync", "Disabled" if not priv.get("cloud_sync") else "Enabled")
        table.add_row("Local Models Only", "Yes" if priv.get("local_models_only") else "No")
        table.add_row("Encryption", "Enabled" if priv.get("encryption_enabled") else "Disabled")

        # Features
        feat = cfg.features
        table.add_row("Memory", "On" if feat.get("memory") else "Off")
        table.add_row("Context Tree", "On" if feat.get("context_tree") else "Off")

        # Paths
        paths = cfg.paths
        table.add_row("Data Dir", str(Path(paths.get("data_dir", "~/.vega/data")).expanduser()))
        table.add_row("ChromaDB Dir", str(Path(paths.get("chromadb_dir", "~/.vega/chromadb")).expanduser()))
    else:
        table.add_row("Config", "[yellow]Not initialised — run [bold]vega init[/bold][/yellow]")

    # API key status
    api_key_path = Path.home() / ".vega" / ".api_key"
    if api_key_path.exists():
        table.add_row("API Key", f"Present ({api_key_path})")
    else:
        table.add_row("API Key", "[yellow]Not configured[/yellow]")

    # Audit stats
    try:
        files = list_log_files()
        total = sum(count_entries(path=f) for f in files)
        table.add_row("Audit Entries", str(total))
    except Exception:
        table.add_row("Audit Entries", "—")

    console.print(table)


# ═════════════════════════════════════════════════════════════════════════
# vega audit
# ═════════════════════════════════════════════════════════════════════════


@main.command()
@click.option("--lines", "-n", default=20, help="Number of recent entries to show.")
@click.option("--file", "-f", "file_path", default=None, help="Specific log file path.")
@click.option("--count", "-c", "count_only", is_flag=True, help="Just show entry count.")
@click.option("--all", "-a", "show_all", is_flag=True, help="List all log files.")
def audit(lines: int, file_path: Optional[str], count_only: bool, show_all: bool) -> None:
    """Show recent audit trail entries."""
    if show_all:
        files = list_log_files()
        if not files:
            console.print("[yellow]No audit log files found.[/yellow]")
            return
        table = Table(title="Audit Log Files")
        table.add_column("File", style="cyan")
        table.add_column("Size", style="white")
        for f in files:
            size = f.stat().st_size
            table.add_row(str(f), f"{size:,} bytes")
        console.print(table)
        return

    if count_only:
        if file_path:
            p = Path(file_path)
            if p.exists():
                console.print(f"Entries in {p}: {count_entries(path=p)}")
            else:
                console.print(f"[red]File not found: {file_path}[/red]")
                sys.exit(1)
        else:
            console.print(f"Entries today: {count_entries()}")
        return

    # Show recent entries
    path = Path(file_path) if file_path else None
    entries = read_recent(lines=lines, path=path)

    if not entries:
        console.print("[yellow]No audit entries found.[/yellow]")
        return

    table = Table(title=f"Recent Audit Entries (last {len(entries)})", box=box.ROUNDED)
    table.add_column("Timestamp", style="dim")
    table.add_column("Action", style="cyan")
    table.add_column("Target", style="white")
    table.add_column("ID", style="yellow")

    for e in entries:
        summary = e.get("data_summary", "")
        why = e.get("why", "")
        model = e.get("model_used", "")
        extra = ""
        if summary:
            extra += f"\n[dim]Data: {summary}[/dim]"
        if why:
            extra += f"\n[dim]Why: {why}[/dim]"
        if model:
            extra += f"\n[dim]Model: {model}[/dim]"

        table.add_row(
            e.get("timestamp", "—"),
            e.get("action", "—"),
            f"{e.get('target', '—')}{extra}",
            e.get("audit_id", "—"),
        )

    console.print(table)


# ═════════════════════════════════════════════════════════════════════════
# vega privacy
# ═════════════════════════════════════════════════════════════════════════


@main.command()
@click.pass_context
def privacy(ctx: click.Context) -> None:
    """Show privacy status, data locations, and configuration."""
    cfg: Optional[Config] = ctx.obj.get("config")
    config_data = cfg.data if cfg else DEFAULT_CONFIG
    priv = config_data.get("privacy", {})

    audit_dir = _audit_dir()
    data_dir = Path(priv.get("data_dir", "~/.vega/data")).expanduser()

    pane = Panel.fit(
        "[bold]Vega Privacy Status[/bold]\n\n"
        "[bold]Configuration[/bold]\n"
        f"  Telemetry:          {'[red]ENABLED[/red]' if priv.get('telemetry') else '[green]DISABLED[/green]'}\n"
        f"  Cloud sync:         {'[red]ENABLED[/red]' if priv.get('cloud_sync') else '[green]DISABLED[/green]'}\n"
        f"  Local models only:  {'[green]Yes[/green]' if priv.get('local_models_only') else '[yellow]No[/yellow]'}\n"
        f"  Audit logging:      {'[green]ENABLED[/green]' if priv.get('audit_log') else '[red]DISABLED[/red]'}\n"
        f"  Encryption:         {'[green]ENABLED[/green]' if priv.get('encryption_enabled') else '[dim]Disabled[/dim]'}\n\n"
        "[bold]Data Locations[/bold]\n"
        f"  Audit directory:  {audit_dir}\n"
        f"  Data directory:   {data_dir}\n\n"
        "[bold]Data Boundary Scopes[/bold]\n"
        "  [cyan]local[/cyan]             — Never leaves this machine\n"
        "  [cyan]context_for_llm[/cyan]   — Local LLM only, not external APIs\n"
        "  [cyan]shareable[/cyan]         — May be sent to external APIs\n\n"
        "[dim]Privacy model: Transparent audit logging + simple boundary types[/dim]\n"
        "[dim](NOT cryptographic provable privacy)[/dim]",
        title="vega privacy",
        border_style="cyan",
    )
    console.print(pane)

    # Audit stats
    try:
        files = list_log_files()
        total_entries = sum(count_entries(path=f) for f in files)
        console.print(f"[dim]Total log files: {len(files)}[/dim]")
        console.print(f"[dim]Total entries: {total_entries}[/dim]")
    except Exception:
        pass

    # Gateway targets
    try:
        from vega.gateway import EXTERNAL_TARGETS, LOCAL_TARGETS
        console.print("\n[bold]External API targets (audited):[/bold]")
        for t in EXTERNAL_TARGETS:
            console.print(f"  [yellow]- {t}[/yellow]")
        console.print("\n[bold]Local targets:[/bold]")
        for t in LOCAL_TARGETS:
            console.print(f"  [green]- {t}[/green]")
    except ImportError:
        pass


# ═════════════════════════════════════════════════════════════════════════
# vega encrypt
# ═════════════════════════════════════════════════════════════════════════


@main.command()
@click.argument("file", required=False)
@click.option("--decrypt", "-d", is_flag=True, help="Decrypt a file instead.")
@click.option("--key", "-k", default=None, help="Encryption key (base64).")
@click.option("--output", "-o", default=None, help="Output file path.")
@click.option("--gen-key", "gen_key", is_flag=True, help="Generate a new key and print it.")
@click.option("--setup", is_flag=True, help="Setup encryption for the Vega data directory.")
@click.pass_context
def encrypt(
    ctx: click.Context,
    file: Optional[str],
    decrypt: bool,
    key: Optional[str],
    output: Optional[str],
    gen_key: bool,
    setup: bool,
) -> None:
    """Encrypt or decrypt a file, or setup local encryption."""
    if setup:
        _encrypt_setup(ctx)
        return

    if gen_key:
        k = generate_key()
        console.print("[green]Generated new Fernet key:[/green]")
        console.print(f"  [bold]{k.decode()}[/bold]")
        console.print("\nStore this key safely. Without it, encrypted data is unrecoverable.")
        return

    if not file:
        console.print("Usage examples:", style="yellow")
        console.print("  vega encrypt myfile.txt                  # encrypt")
        console.print("  vega encrypt myfile.txt --decrypt        # decrypt")
        console.print("  vega encrypt --gen-key                   # generate a key")
        console.print("  vega encrypt --setup                     # setup encryption")
        sys.exit(1)

    src = Path(file)
    if not src.exists():
        console.print(f"[red]File not found: {file}[/red]")
        sys.exit(1)

    key_bytes = None
    if key:
        import base64
        try:
            key_bytes = key.encode("utf-8")
            base64.urlsafe_b64decode(key_bytes + b"==")
        except Exception:
            console.print("[red]Invalid key format. Expected base64-encoded Fernet key.[/red]")
            sys.exit(1)
    else:
        key_str = click.prompt("Enter encryption key", hide_input=True)
        key_bytes = key_str.encode("utf-8")

    dst = output
    if not dst:
        if decrypt:
            dst = str(src) + ".decrypted"
        else:
            dst = str(src) + ".encrypted"

    try:
        if decrypt:
            decrypt_file(str(src), key_bytes, dst)
            console.print(f"[green]Decrypted to:[/green] {dst}")
        else:
            used_key = encrypt_file(str(src), dst, key_bytes)
            console.print(f"[green]Encrypted to:[/green] {dst}")
            if not key:
                console.print(f"Key: [bold]{used_key.decode()}[/bold]")
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        sys.exit(1)


def _encrypt_setup(ctx: click.Context) -> None:
    """Interactive setup for encrypting the Vega data directory."""
    console.print(Panel.fit(
        "[bold]Encryption Setup[/bold]\n\n"
        "This will generate a Fernet encryption key and store it in your\n"
        "config. Enable encryption at rest for your Vega data directory.",
        title="vega encrypt --setup",
    ))

    key_path = Path.home() / ".vega" / "encryption.key"
    if key_path.exists():
        if not click.confirm("Encryption key already exists. Overwrite?", default=False):
            console.print("[dim]Aborted.[/dim]")
            return

    key = generate_key()
    key_path.write_bytes(key)
    key_path.chmod(0o600)
    console.print(f"[green]✓ Key saved to {key_path} (mode 600)[/green]")

    # Update config
    cfg: Optional[Config] = ctx.obj.get("config")
    if cfg:
        cfg.data.setdefault("privacy", {})["encryption_enabled"] = True
        cfg.data.setdefault("paths", {})["encryption_key_path"] = str(key_path)
        cfg.save()
        console.print("[green]✓ Encryption enabled in config[/green]")
    else:
        console.print("[yellow]Config not loaded — run [bold]vega init[/bold] first.[/yellow]")


# ═════════════════════════════════════════════════════════════════════════
# vega migrate
# ═════════════════════════════════════════════════════════════════════════


@main.command()
@click.option("--from-obsidian", "obsidian_path", type=click.Path(exists=True, file_okay=False),
              help="Import an Obsidian vault (path to vault directory).")
@click.option("--dry-run", is_flag=True, help="Show what would be imported without importing.")
def migrate(obsidian_path: Optional[str], dry_run: bool) -> None:
    """Import data from external sources into Vega.

    Currently supported:

    * Obsidian vaults (``--from-obsidian /path/to/vault``)
    """
    if obsidian_path:
        _migrate_obsidian(Path(obsidian_path), dry_run)
    else:
        console.print("[yellow]No migration source specified.[/yellow]")
        console.print("  Usage: vega migrate --from-obsidian /path/to/vault")
        sys.exit(1)


def _migrate_obsidian(vault_path: Path, dry_run: bool) -> None:
    """Import an Obsidian vault into the Vega context tree."""
    console.print(Panel.fit(
        f"[bold]Importing Obsidian Vault[/bold]\n{vault_path}",
        title="vega migrate",
    ))

    # Check it looks like an Obsidian vault
    has_obsidian_dir = (vault_path / ".obsidian").is_dir()
    md_files = list(vault_path.rglob("*.md"))
    if not has_obsidian_dir and not md_files:
        console.print("[red]That doesn't look like an Obsidian vault — no .obsidian dir or .md files found.[/red]")
        sys.exit(1)

    console.print(f"  Markdown files found: {len(md_files)}")

    if dry_run:
        console.print("[yellow]Dry run — no files imported.[/yellow]")
        # Show first few files
        for f in md_files[:10]:
            rel = f.relative_to(vault_path)
            size = f.stat().st_size
            console.print(f"  [dim]{rel}[/dim] ({size} bytes)")
        if len(md_files) > 10:
            console.print(f"  [dim]... and {len(md_files) - 10} more[/dim]")
        return

    # Actual import via context_tree migration
    try:
        from vega.context_tree.db import ContextTreeDB
        from vega.context_tree.migration import migrate_from_obsidian
    except ImportError:
        console.print("[yellow]Context tree migration module not yet available. Installing ...[/yellow]")
        console.print("[yellow]Fallback: copying files to data directory.[/yellow]")
        _fallback_obsidian_import(vault_path, md_files)
        return

    try:
        db = ContextTreeDB()
        db.initialize()
        report = migrate_from_obsidian(db, str(vault_path))
        console.print(f"[green]✓ Imported {report.nodes_created} nodes, {report.edges_created} edges[/green]")
        if report.errors:
            console.print(f"[yellow]{len(report.errors)} warnings/errors during import[/yellow]")
            for err in report.errors[:5]:
                console.print(f"  [dim]{err}[/dim]")
    except Exception as exc:
        console.print(f"[red]Migration failed: {exc}[/red]")
        console.print("[yellow]Falling back to file copy ...[/yellow]")
        _fallback_obsidian_import(vault_path, md_files)


def _fallback_obsidian_import(vault_path: Path, md_files: list[Path]) -> None:
    """Copy markdown files into the Vega data directory as a fallback."""
    import shutil
    dest_base = Path.home() / ".vega" / "data" / "obsidian_import" / vault_path.name
    dest_base.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in md_files:
        rel = src.relative_to(vault_path)
        dest = dest_base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        count += 1

    # Log to audit
    try:
        log_audit(
            action="obsidian_import",
            target=str(vault_path),
            data_summary=f"Imported {count} files to {dest_base}",
            why="User requested Obsidian vault import",
        )
    except Exception:
        pass

    console.print(f"[green]✓ Copied {count} files to {dest_base}[/green]")
    console.print("  Run [bold]vega status[/bold] to verify.")


# ═════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
