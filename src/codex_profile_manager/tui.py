from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, OptionList, Static

from .footprint import build_footprint_report
from .operations import ManagerError, ProfileManager


@dataclass(slots=True)
class PaneItem:
    key: str
    label: str


class ProfileNameScreen(ModalScreen[str | None]):
    CSS = """
    SaveProfileScreen {
        align: center middle;
    }

    #save-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }

    #save-actions {
        height: auto;
        padding-top: 1;
    }

    #save-actions Static {
        width: 1fr;
        content-align: center middle;
        padding: 0 1;
        border: round $panel-lighten-1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        title: str = "Save current selection as a profile",
        placeholder: str = "Profile name",
        initial_value: str = "",
    ) -> None:
        super().__init__()
        self.title = title
        self.placeholder = placeholder
        self.initial_value = initial_value

    def compose(self) -> ComposeResult:
        with Vertical(id="save-dialog"):
            yield Label(self.title)
            yield Input(value=self.initial_value, placeholder=self.placeholder, id="profile-name")
            with Horizontal(id="save-actions"):
                yield Static("Enter: Save", classes="action")
                yield Static("Esc: Cancel", classes="action")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted, "#profile-name")
    def submit_name(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)


class ConfirmScreen(ModalScreen[bool]):
    CSS = """
    ConfirmScreen {
        align: center middle;
    }

    #confirm-dialog {
        width: 64;
        height: auto;
        padding: 1 2;
        border: round $warning;
        background: $surface;
    }

    #confirm-actions {
        height: auto;
        padding-top: 1;
    }

    #confirm-actions Static {
        width: 1fr;
        content-align: center middle;
        padding: 0 1;
        border: round $panel-lighten-1;
    }
    """

    BINDINGS = [
        ("y", "confirm", "Confirm"),
        ("n", "cancel", "Cancel"),
        ("enter", "confirm", "Confirm"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(self.prompt)
            with Horizontal(id="confirm-actions"):
                yield Static("Enter / y: Confirm", classes="action")
                yield Static("Esc / n: Cancel", classes="action")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class ReportScreen(ModalScreen[None]):
    CSS = """
    ReportScreen {
        align: center middle;
    }

    #report-dialog {
        width: 110;
        height: 85%;
        border: round $accent;
        background: $surface;
    }

    #report-title {
        height: auto;
        padding: 0 1;
        text-style: bold;
        background: $boost;
    }

    #report-scroll {
        height: 1fr;
        padding: 1 2;
    }

    #report-body {
        width: 100%;
    }

    #report-footer {
        height: auto;
        padding: 0 1 1 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("enter", "close", "Close"),
        ("q", "close", "Close"),
        ("f", "close", "Close"),
    ]

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.title = title
        self.body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="report-dialog"):
            yield Static(self.title, id="report-title")
            with VerticalScroll(id="report-scroll"):
                yield Static(self.body, id="report-body")
            yield Static("Esc / Enter / q / f closes this report", id="report-footer")

    def action_close(self) -> None:
        self.dismiss(None)


class TextualProfileApp(App[None]):
    TITLE = "Pluskints"

    CSS = """
    Screen {
        layout: vertical;
    }

    #main {
        height: 1fr;
    }

    .pane {
        width: 1fr;
        min-width: 24;
        border: round $panel;
    }

    #profiles-pane {
        width: 28;
    }

    #preview-pane {
        height: 12;
        border: round $accent;
        padding: 0 1;
    }

    .pane-title {
        text-style: bold;
        padding: 0 1;
        background: $boost;
    }

    OptionList {
        height: 1fr;
    }

    #preview-body {
        height: 1fr;
        overflow-y: auto;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("space", "toggle_selected", "Toggle", priority=True),
        Binding("enter", "load_profile", "Load Profile", priority=True),
        Binding("a", "apply_changes", "Apply", priority=True),
        Binding("d", "preview_changes", "Dry Run", priority=True),
        Binding("f", "show_footprint", "Context Footprint", priority=True),
        Binding("s", "save_profile_as", "Save As", priority=True),
        Binding("w", "write_profile", "Write Profile", priority=True),
        Binding("x", "delete_profile", "Delete Profile", priority=True),
        Binding("r", "reload_state", "Reload", priority=True),
    ]

    def __init__(self, manager: ProfileManager) -> None:
        super().__init__()
        self.manager = manager
        self.profile_items: list[PaneItem] = []
        self.skill_items: list[PaneItem] = []
        self.plugin_items: list[PaneItem] = []
        self.working_skills: set[str] = set()
        self.working_plugins: set[str] = set()
        self.loaded_profile_name: str | None = None
        self.pending_write_profile_name: str | None = None
        self.pending_delete_profile_name: str | None = None
        self.message = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="main"):
            with Vertical(id="profiles-pane", classes="pane"):
                yield Static("Profiles", classes="pane-title", id="profiles-title")
                yield OptionList(id="profiles")
            with Vertical(id="skills-pane", classes="pane"):
                yield Static("Skills", classes="pane-title", id="skills-title")
                yield OptionList(id="skills")
            with Vertical(id="plugins-pane", classes="pane"):
                yield Static("Plugins", classes="pane-title", id="plugins-title")
                yield OptionList(id="plugins")
        with Vertical(id="preview-pane"):
            yield Static("Workspace", classes="pane-title", id="preview-title")
            yield Static(id="preview-body")
        yield Footer()

    def on_mount(self) -> None:
        self._load_state(reset_working=True)
        self.query_one("#profiles", OptionList).focus()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        modal_open = isinstance(self.screen, (ProfileNameScreen, ConfirmScreen))
        if modal_open:
            blocked_actions = {
                "toggle_selected",
                "load_profile",
                "apply_changes",
                "preview_changes",
                "show_footprint",
                "save_profile_as",
                "write_profile",
                "delete_profile",
                "reload_state",
                "quit",
            }
            if action in blocked_actions:
                return False
        if isinstance(self.focused, Input):
            blocked_actions = {
                "toggle_selected",
                "load_profile",
                "apply_changes",
                "preview_changes",
                "show_footprint",
                "save_profile_as",
                "write_profile",
                "delete_profile",
                "reload_state",
                "quit",
            }
            if action in blocked_actions:
                return False
        return True

    @on(OptionList.OptionSelected, "#profiles")
    def load_profile_from_list(self, event: OptionList.OptionSelected) -> None:
        self._load_profile(event.option_index)

    def action_save_profile_as(self) -> None:
        self.push_screen(
            ProfileNameScreen(
                title="Save current working selection as a profile",
                placeholder="Profile name",
                initial_value=self.loaded_profile_name or "",
            ),
            self._handle_save_profile_as,
        )

    def action_write_profile(self) -> None:
        name = self._selected_profile_name()
        if not name:
            self._set_message("No profile selected.")
            return
        self.pending_write_profile_name = name
        self.push_screen(
            ConfirmScreen(f"Overwrite profile '{name}' with the current working selection?"),
            self._handle_write_profile_confirmation,
        )

    def action_delete_profile(self) -> None:
        name = self._selected_profile_name()
        if not name:
            self._set_message("No profile selected.")
            return
        self.pending_delete_profile_name = name
        self.push_screen(
            ConfirmScreen(f"Delete profile '{name}'? This removes only the saved profile."),
            self._handle_delete_profile_confirmation,
        )

    def action_reload_state(self) -> None:
        self._load_state(reset_working=True)
        self._set_message("Reloaded from disk.")

    def action_toggle_selected(self) -> None:
        focused = self.focused
        if isinstance(focused, OptionList) and focused.id == "skills":
            option_list = self.query_one("#skills", OptionList)
            if option_list.highlighted is None or option_list.highlighted >= len(self.skill_items):
                return
            skill = self.skill_items[option_list.highlighted].key
            if skill in self.working_skills:
                self.working_skills.remove(skill)
            else:
                self.working_skills.add(skill)
            self.message = ""
            self._refresh_profile_list()
            self._refresh_skill_list()
            self._update_preview()
        elif isinstance(focused, OptionList) and focused.id == "plugins":
            option_list = self.query_one("#plugins", OptionList)
            if option_list.highlighted is None or option_list.highlighted >= len(self.plugin_items):
                return
            plugin_id = self.plugin_items[option_list.highlighted].key
            if plugin_id in self.working_plugins:
                self.working_plugins.remove(plugin_id)
            else:
                self.working_plugins.add(plugin_id)
            self.message = ""
            self._refresh_profile_list()
            self._refresh_plugin_list()
            self._update_preview()
        else:
            self._set_message("Space toggles items only when the Skills or Plugins pane is focused.")

    def action_load_profile(self) -> None:
        option_list = self.query_one("#profiles", OptionList)
        if option_list.highlighted is None:
            return
        self._load_profile(option_list.highlighted)

    def action_preview_changes(self) -> None:
        self._update_preview(force_plan=True)

    def action_show_footprint(self) -> None:
        report = build_footprint_report(self.manager.config)
        sorted_skills = sorted(
            report.skills,
            key=lambda skill: (-skill.estimated_tokens, skill.label),
        )
        sorted_plugins = sorted(
            report.plugins,
            key=lambda plugin: (-plugin.estimated_tokens, plugin.label),
        )
        lines = [
            "Context Footprint",
            "",
            f"  Skills total    {len(report.skill_totals.files):>3} files   {report.skill_totals.estimated_tokens:>8} est. tokens",
            f"  Plugins total   {len(report.plugin_totals.files):>3} files   {report.plugin_totals.estimated_tokens:>8} est. tokens",
            f"  Overall total   {len(report.overall.files):>3} files   {report.overall.estimated_tokens:>8} est. tokens",
            "",
            "All skills",
        ]
        if sorted_skills:
            for skill in sorted_skills:
                lines.append(
                    f"  [{skill.status:<8}] {skill.label:<36} {skill.estimated_tokens:>8} est. tokens"
                )
        else:
            lines.append("  No discovered skills.")
        lines.extend(["", "All plugins"])
        if sorted_plugins:
            for plugin in sorted_plugins:
                lines.append(
                    f"  [{plugin.status:<8}] {plugin.label:<36} {plugin.estimated_tokens:>8} est. tokens"
                )
        else:
            lines.append("  No configured plugins.")
        if report.warnings:
            lines.extend(["", "Warnings"])
            lines.extend(f"  - {warning}" for warning in report.warnings[:5])
        lines.extend(
            [
                "",
                "Estimate based on discovered SKILL.md files only.",
            ]
        )
        self.push_screen(ReportScreen("Context Footprint Report", "\n".join(lines)))

    def action_apply_changes(self) -> None:
        try:
            plan = self.manager.build_plan(self.working_skills, self.working_plugins)
            self.manager.apply_plan(plan)
            self._load_state(reset_working=True)
            self._set_message("Applied changes. Start a new Codex session for this to take effect.")
        except ManagerError as exc:
            self._set_message(str(exc))

    def _load_state(self, reset_working: bool) -> None:
        state = self.manager.refresh()
        self.profile_items = [
            PaneItem(name, name) for name in sorted(self.manager.config.profiles)
        ]
        self.skill_items = [
            PaneItem(skill.name, self._format_skill_label(skill.name))
            for skill in state.skills
        ]
        self.plugin_items = [
            PaneItem(plugin.plugin_id, self._format_plugin_label(plugin.plugin_id))
            for plugin in state.plugins
        ]
        if reset_working:
            self.working_skills = set(state.active_skill_names)
            self.working_plugins = set(state.enabled_plugin_ids)
            self.loaded_profile_name = None
        self._refresh_titles()
        self._refresh_profile_list()
        self._refresh_skill_list()
        self._refresh_plugin_list()
        self._update_preview()

    def _refresh_profile_list(self) -> None:
        profile_list = self.query_one("#profiles", OptionList)
        highlighted = self._safe_highlight(profile_list, len(self.profile_items))
        self.profile_items = [
            PaneItem(item.key, self._format_profile_label(item.key)) for item in self.profile_items
        ]
        profile_list.clear_options()
        profile_list.add_options([item.label for item in self.profile_items])
        if self.profile_items:
            profile_list.highlighted = highlighted

    def _refresh_skill_list(self) -> None:
        skill_list = self.query_one("#skills", OptionList)
        highlighted = self._safe_highlight(skill_list, len(self.skill_items))
        self.skill_items = [
            PaneItem(item.key, self._format_skill_label(item.key)) for item in self.skill_items
        ]
        skill_list.clear_options()
        skill_list.add_options([item.label for item in self.skill_items])
        if self.skill_items:
            skill_list.highlighted = highlighted

    def _refresh_plugin_list(self) -> None:
        plugin_list = self.query_one("#plugins", OptionList)
        highlighted = self._safe_highlight(plugin_list, len(self.plugin_items))
        self.plugin_items = [
            PaneItem(item.key, self._format_plugin_label(item.key)) for item in self.plugin_items
        ]
        plugin_list.clear_options()
        plugin_list.add_options([item.label for item in self.plugin_items])
        if self.plugin_items:
            plugin_list.highlighted = highlighted

    def _load_profile(self, index: int) -> None:
        if index >= len(self.profile_items):
            self._set_message("No profile selected.")
            return
        name = self.profile_items[index].key
        try:
            plan = self.manager.build_profile_plan(name)
        except ManagerError as exc:
            self._set_message(str(exc))
            return
        self.working_skills = set(plan.desired_skills)
        self.working_plugins = set(plan.desired_plugins)
        self.loaded_profile_name = name
        self._refresh_titles()
        self._refresh_profile_list()
        self._refresh_skill_list()
        self._refresh_plugin_list()
        self._set_message(
            "\n".join(
                [
                    "Profile Activated",
                    "",
                    f"  Name             {name}",
                    f"  Working skills   {len(self.working_skills)} selected",
                    f"  Working plugins  {len(self.working_plugins)} selected",
                    "",
                    "This is now the active working set in Pluskints.",
                    "Press w to save edits back to this profile, or a to apply to disk.",
                ]
            )
        )
        self.notify(f"Activated profile: {name}", title="Pluskints")

    def _update_preview(self, force_plan: bool = False) -> None:
        preview = self.query_one("#preview-body", Static)
        profile_text = self.loaded_profile_name or "none"
        profile_state = (
            "modified"
            if self.loaded_profile_name and self._loaded_profile_is_dirty()
            else "clean"
            if self.loaded_profile_name
            else "n/a"
        )
        help_text = "\n".join(
            [
                "Controls",
                "",
                "  Navigation",
                "    Tab / Shift+Tab   move focus across panes",
                "    Arrow keys        move within the focused pane",
                "",
                "  Profiles",
                "    Enter             load selected profile into the working set",
                "    w                 overwrite the selected profile after confirmation",
                "    s                 save the working set as a new or renamed profile",
                "    x                 delete the selected saved profile after confirmation",
                "",
                "  Working Set",
                "    Space             toggle the focused skill or plugin",
                "",
                "  Session",
                "    a                 apply current working set to disk",
                "    d                 show pending diff",
                "    f                 open the Context Footprint report",
                "    r                 reload from disk",
                "    q                 quit",
            ]
        )
        status_text = "\n".join(
            [
                "Status",
                "",
                f"  Editing profile   {profile_text}",
                f"  Profile state     {profile_state}",
                f"  Working skills    {len(self.working_skills)} selected",
                f"  Working plugins   {len(self.working_plugins)} selected",
            ]
        )
        if self.message and not force_plan:
            preview.update(f"{status_text}\n\n{self.message}\n\n{help_text}")
            return
        try:
            plan = self.manager.build_plan(self.working_skills, self.working_plugins)
            body = self.manager.render_plan(plan)
        except ManagerError as exc:
            body = str(exc)
        preview.update(
            "\n".join(
                [
                    status_text,
                    "",
                    "Pending Changes",
                    "",
                    body,
                    "",
                    help_text,
                ]
            )
        )

    def _set_message(self, message: str) -> None:
        self.message = message
        self._update_preview()

    def _refresh_titles(self) -> None:
        profiles_title = self.query_one("#profiles-title", Static)
        preview_title = self.query_one("#preview-title", Static)
        loaded = self.loaded_profile_name or "none"
        profiles_title.update(f"Profiles  Loaded: {loaded}")
        preview_title.update("Workspace")

    def _handle_save_profile_as(self, name: str | None) -> None:
        if not name:
            self._set_message("Profile save cancelled.")
            return
        self.manager.save_profile(name, self.working_skills, self.working_plugins)
        self.loaded_profile_name = name
        self._load_state(reset_working=False)
        self._set_message(f"Saved profile: {name}")

    def _handle_write_profile_confirmation(self, confirmed: bool | None) -> None:
        name = self.pending_write_profile_name
        self.pending_write_profile_name = None
        if not confirmed or not name:
            self._set_message("Profile write cancelled.")
            return
        self.manager.save_profile(name, self.working_skills, self.working_plugins)
        self.loaded_profile_name = name
        self._load_state(reset_working=False)
        self._set_message(f"Wrote working selection to profile: {name}")

    def _handle_delete_profile_confirmation(self, confirmed: bool | None) -> None:
        name = self.pending_delete_profile_name
        self.pending_delete_profile_name = None
        if not confirmed or not name:
            self._set_message("Profile delete cancelled.")
            return
        try:
            self.manager.delete_profile(name)
        except KeyError as exc:
            self._set_message(str(exc))
            return
        if self.loaded_profile_name == name:
            self.loaded_profile_name = None
        self._load_state(reset_working=False)
        self._set_message(f"Deleted profile: {name}")

    def _format_skill_label(self, name: str) -> str:
        return f"[{'x' if name in self.working_skills else ' '}] {name}"

    def _format_plugin_label(self, plugin_id: str) -> str:
        return f"[{'x' if plugin_id in self.working_plugins else ' '}] {plugin_id}"

    def _format_profile_label(self, name: str) -> str:
        if name != self.loaded_profile_name:
            return f"[ ] {name}"
        state = "modified" if self._loaded_profile_is_dirty() else "clean"
        marker = "!" if state == "modified" else "*"
        return f"[{marker}] {name} ({state})"

    def _selected_profile_name(self) -> str | None:
        profile_list = self.query_one("#profiles", OptionList)
        if profile_list.highlighted is None or profile_list.highlighted >= len(self.profile_items):
            return self.loaded_profile_name
        return self.profile_items[profile_list.highlighted].key

    @staticmethod
    def _safe_highlight(option_list: OptionList, item_count: int) -> int:
        if item_count <= 0:
            return 0
        highlighted = option_list.highlighted or 0
        return max(0, min(item_count - 1, highlighted))

    def _loaded_profile_is_dirty(self) -> bool:
        if not self.loaded_profile_name:
            return False
        profile = self.manager.config.profiles.get(self.loaded_profile_name)
        if profile is None:
            return False
        state = self.manager.refresh()
        return (
            set(self.manager.build_profile_plan(self.loaded_profile_name).desired_skills)
            != self.working_skills
            or set(self.manager.build_profile_plan(self.loaded_profile_name).desired_plugins)
            != self.working_plugins
        )


def run_tui(manager: ProfileManager) -> None:
    TextualProfileApp(manager).run()
