from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .footprint import build_footprint_report
from .operations import ManagerError, ProfileManager
from .tui import run_tui

app = typer.Typer(
    no_args_is_help=True,
    help="Manage Codex skill and plugin profiles for the next Codex session. Preferred command: pluskints.",
)
profile_app = typer.Typer(help="Inspect, save, and apply named skill/plugin profiles.")
app.add_typer(profile_app, name="profile")
console = Console()


def manager_from_path(config_path: Path | None) -> ProfileManager:
    return ProfileManager(config_path=config_path)


def restart_note() -> None:
    console.print("[bold yellow]Start a new Codex session for this to take effect.[/bold yellow]")


@app.command("list", help="List discovered skills, plugins, profiles, or all three.")
def list_items(
    kind: str = typer.Option("all", help="One of: all, skills, plugins, profiles."),
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    state = manager.refresh()

    if kind in {"all", "skills"}:
        table = Table(title="Skills")
        table.add_column("Skill")
        table.add_column("Active")
        table.add_column("Installed")
        table.add_column("Source")
        for skill in state.skills:
            table.add_row(
                skill.name,
                "yes" if skill.active else "no",
                "yes" if skill.installed else "no",
                skill.source or "-",
            )
        console.print(table)

    if kind in {"all", "plugins"}:
        table = Table(title="Plugins")
        table.add_column("Plugin")
        table.add_column("Enabled")
        for plugin in state.plugins:
            table.add_row(plugin.plugin_id, "yes" if plugin.enabled else "no")
        console.print(table)

    if kind in {"all", "profiles"}:
        table = Table(title="Profiles")
        table.add_column("Profile")
        table.add_column("Skills")
        table.add_column("Plugins")
        for name, profile in sorted(manager.config.profiles.items()):
            table.add_row(name, ", ".join(profile.enabled_skills), ", ".join(profile.enabled_plugins))
        console.print(table)


@app.command(help="Show the current active skill and plugin state.")
def status(
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    state = manager.refresh()
    console.print(f"Config: {manager.config_path}")
    console.print(f"Active skills: {len(state.active_skill_names)}")
    console.print(f"Disabled skills: {len(state.disabled_skill_names)}")
    console.print(f"Enabled plugins: {len(state.enabled_plugin_ids)} / {len(state.plugins)}")

    skill_table = Table(title="Active Skills")
    skill_table.add_column("Skill")
    for name in sorted(state.active_skill_names):
        skill_table.add_row(name)
    console.print(skill_table)

    plugin_table = Table(title="Enabled Plugins")
    plugin_table.add_column("Plugin")
    for plugin_id in sorted(state.enabled_plugin_ids):
        plugin_table.add_row(plugin_id)
    console.print(plugin_table)


@app.command(help="Check for config drift, missing directories, and lockfile mismatches.")
def doctor(
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    issues = manager.doctor()
    if not issues:
        console.print("[green]No issues detected.[/green]")
        return
    for issue in issues:
        console.print(f"- {issue}")


@app.command(help="Estimate skill/plugin context footprint from discovered SKILL.md files.")
def footprint(
    show_files: bool = typer.Option(False, "--show-files", help="Include per-skill and per-plugin skill file rows."),
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    report = build_footprint_report(manager.config)
    sorted_skills = sorted(
        report.skills,
        key=lambda skill: (-skill.estimated_tokens, skill.label),
    )
    sorted_plugins = sorted(
        report.plugins,
        key=lambda plugin: (-plugin.estimated_tokens, plugin.label),
    )

    summary = Table(title="Estimated Context Footprint")
    summary.add_column("Group")
    summary.add_column("Files", justify="right")
    summary.add_column("Bytes", justify="right")
    summary.add_column("Lines", justify="right")
    summary.add_column("Est. Tokens", justify="right")
    summary.add_row(
        report.skill_totals.label,
        str(len(report.skill_totals.files)),
        str(report.skill_totals.bytes),
        str(report.skill_totals.lines),
        str(report.skill_totals.estimated_tokens),
    )
    summary.add_row(
        report.plugin_totals.label,
        str(len(report.plugin_totals.files)),
        str(report.plugin_totals.bytes),
        str(report.plugin_totals.lines),
        str(report.plugin_totals.estimated_tokens),
    )
    summary.add_row(
        report.overall.label,
        str(len(report.overall.files)),
        str(report.overall.bytes),
        str(report.overall.lines),
        str(report.overall.estimated_tokens),
    )
    console.print(summary)

    skills_table = Table(title="All Skills")
    skills_table.add_column("Skill")
    skills_table.add_column("Status")
    skills_table.add_column("Files", justify="right")
    skills_table.add_column("Bytes", justify="right")
    skills_table.add_column("Est. Tokens", justify="right")
    for skill in sorted_skills:
        skills_table.add_row(
            skill.label,
            skill.status,
            str(len(skill.files)),
            str(skill.bytes),
            str(skill.estimated_tokens),
        )
    console.print(skills_table)

    plugin_table = Table(title="All Plugins")
    plugin_table.add_column("Plugin")
    plugin_table.add_column("Status")
    plugin_table.add_column("Files", justify="right")
    plugin_table.add_column("Bytes", justify="right")
    plugin_table.add_column("Est. Tokens", justify="right")
    for plugin in sorted_plugins:
        plugin_table.add_row(
            plugin.label,
            plugin.status,
            str(len(plugin.files)),
            str(plugin.bytes),
            str(plugin.estimated_tokens),
        )
    console.print(plugin_table)

    if show_files:
        files_table = Table(title="Measured Files")
        files_table.add_column("Label")
        files_table.add_column("Bytes", justify="right")
        files_table.add_column("Lines", justify="right")
        files_table.add_column("Est. Tokens", justify="right")
        files_table.add_column("Path")
        for skill in sorted_skills:
            for file_info in skill.files:
                files_table.add_row(
                    f"{skill.status}:{file_info.label}",
                    str(file_info.bytes),
                    str(file_info.lines),
                    str(file_info.estimated_tokens),
                    str(file_info.path),
                )
        for plugin in sorted_plugins:
            for file_info in plugin.files:
                files_table.add_row(
                    f"{plugin.status}:{file_info.label}",
                    str(file_info.bytes),
                    str(file_info.lines),
                    str(file_info.estimated_tokens),
                    str(file_info.path),
                )
        console.print(files_table)

    if report.warnings:
        console.print("Warnings:")
        for warning in report.warnings:
            console.print(f"- {warning}")
    console.print(
        "This is an estimate based on discovered SKILL.md files, not a guarantee of exact prompt tokens."
    )


@app.command(help="Enable a skill or plugin in the current on-disk state. Does not update saved profiles.")
def enable(
    name: str,
    kind: str = typer.Option("auto", help="One of: auto, skill, plugin."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    try:
        plan = manager.enable(name, kind=kind, dry_run=dry_run)
    except ManagerError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1)
    console.print(manager.render_plan(plan))
    if not dry_run:
        restart_note()


@app.command(help="Disable a skill or plugin in the current on-disk state. Does not update saved profiles.")
def disable(
    name: str,
    kind: str = typer.Option("auto", help="One of: auto, skill, plugin."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    try:
        plan = manager.disable(name, kind=kind, dry_run=dry_run)
    except ManagerError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1)
    console.print(manager.render_plan(plan))
    if not dry_run:
        restart_note()


@profile_app.command("diff", help="Preview what would change if a named profile were applied.")
def profile_diff(
    name: str,
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    try:
        plan = manager.build_profile_plan(name)
    except (KeyError, ManagerError) as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1)
    console.print(manager.render_plan(plan))


@profile_app.command("apply", help="Apply a named profile to the current on-disk state. Use --dry-run to preview only.")
def profile_apply(
    name: str,
    dry_run: bool = typer.Option(False, "--dry-run"),
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    try:
        plan = manager.build_profile_plan(name)
        manager.apply_plan(plan, dry_run=dry_run)
    except (KeyError, ManagerError) as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1)
    console.print(manager.render_plan(plan))
    if not dry_run:
        restart_note()


@profile_app.command("save", help="Save the current active skills and plugins as a named profile.")
def profile_save_cmd(
    name: str,
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    manager.save_profile(name)
    console.print(f"Saved profile: {name}")


@profile_app.command("create", help="Create a new empty profile or seed it from the current active state.")
def profile_create(
    name: str,
    from_current: bool = typer.Option(False, "--from-current", help="Start with the current active skills and plugins."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace an existing profile with the same name."),
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    try:
        profile = manager.create_profile(name, from_current=from_current, overwrite=overwrite)
    except ValueError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1)
    console.print(f"Created profile: {profile.name}")


@profile_app.command("add", help="Add a skill or plugin to a named profile.")
def profile_add(
    profile_name: str,
    item_name: str,
    kind: str = typer.Option("auto", help="One of: auto, skill, plugin."),
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    try:
        profile = manager.add_to_profile(profile_name, item_name, kind=kind)
    except (KeyError, ManagerError) as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1)
    console.print(f"Updated profile: {profile.name}")


@profile_app.command("remove", help="Remove a skill or plugin from a named profile.")
def profile_remove(
    profile_name: str,
    item_name: str,
    kind: str = typer.Option("auto", help="One of: auto, skill, plugin."),
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    try:
        profile = manager.remove_from_profile(profile_name, item_name, kind=kind)
    except (KeyError, ManagerError) as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1)
    console.print(f"Updated profile: {profile.name}")


@profile_app.command("delete", help="Delete a named profile from the saved config.")
def profile_delete(
    name: str,
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    try:
        profile = manager.delete_profile(name)
    except KeyError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1)
    console.print(f"Deleted profile: {profile.name}")


@app.command(help="Write a JSON snapshot of the current skill and plugin state.")
def backup(
    output_path: Path | None = typer.Argument(None),
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = Path.cwd() / f"codex-profile-backup-{timestamp}.json"
    path = manager.backup(output_path)
    console.print(f"Backup written to {path}")


@app.command(help="Restore skills and plugins from a saved JSON snapshot. Use --dry-run to preview only.")
def restore(
    snapshot_path: Path,
    dry_run: bool = typer.Option(False, "--dry-run"),
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    try:
        plan = manager.restore(snapshot_path, dry_run=dry_run)
    except ManagerError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(1)
    console.print(manager.render_plan(plan))
    if not dry_run:
        restart_note()


@app.command(help="Open the interactive Textual terminal UI.")
def tui(
    config_path: Path | None = typer.Option(None, "--config-path"),
) -> None:
    manager = manager_from_path(config_path)
    run_tui(manager)


if __name__ == "__main__":
    app()
