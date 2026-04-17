# codex-profile-manager

Terminal profile manager for Codex that prepares the next session by enabling and disabling:

- user-installed skills under `~/.agents/skills`
- Codex plugins declared in `~/.codex/config.toml`

This project does not try to mutate the current live Codex session. It updates on-disk state and prints a reminder to start a new session.

## What It Does

- Discovers installed and active skills from:
  - `~/.agents/.skill-lock.json`
  - `~/.agents/skills`
  - `~/.agents/skills.disabled`
- Discovers plugin state from:
  - `~/.codex/config.toml`
- Saves named profiles for skill and plugin selections
- Applies profiles with a dry-run diff first if desired
- Backs up and restores current state
- Provides:
  - a CLI
  - a Textual TUI

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The package exposes `codex-prof`.

## Quick Start

```bash
codex-prof status
codex-prof list
codex-prof profile diff minimal
codex-prof profile apply minimal --dry-run
codex-prof tui
```

## Default Config

On first run the app creates:

`~/.config/codex-profile-manager/config.json`

Example:

```json
{
  "skills_dir": "/home/you/.agents/skills",
  "disabled_dir": "/home/you/.agents/skills.disabled",
  "skill_lock_path": "/home/you/.agents/.skill-lock.json",
  "codex_config_path": "/home/you/.codex/config.toml",
  "profiles": {
    "minimal": {
      "enabled_skills": ["find-skills"],
      "enabled_plugins": []
    },
    "coding": {
      "enabled_skills": ["supabase", "supabase-postgres-best-practices"],
      "enabled_plugins": [
        "github@openai-curated",
        "build-web-apps@openai-curated",
        "vercel@openai-curated"
      ]
    },
    "full": {
      "enabled_skills": ["*"],
      "enabled_plugins": ["*"]
    }
  }
}
```

## CLI

```bash
codex-prof list
codex-prof status
codex-prof doctor
codex-prof footprint
codex-prof footprint --show-files

codex-prof enable supabase
codex-prof disable find-skills

codex-prof enable github@openai-curated --kind plugin
codex-prof disable vercel@openai-curated --kind plugin

codex-prof profile diff coding
codex-prof profile apply coding
codex-prof profile save web-work
codex-prof profile create backend --from-current
codex-prof profile add backend supabase --kind skill
codex-prof profile add backend github@openai-curated --kind plugin
codex-prof profile remove backend find-skills --kind skill
codex-prof profile delete backend

codex-prof backup
codex-prof restore backup.json --dry-run

codex-prof tui
```

## TUI

The Textual app is named `Pluskints` and is built for interactive profile editing.

- `Tab` / `Shift+Tab`: move focus
- arrow keys: move selection
- `Enter`: load selected profile
- `Space`: toggle selected skill or plugin
- `w`: write the current working selection back to the selected profile
- `x`: delete the selected saved profile after confirmation
- `a`: apply pending changes
- `d`: show dry-run preview
- `f`: open the Context Footprint report
- `s`: save the current working selection as a profile name you choose
- `r`: reload from disk
- `q`: quit

Profile editing flow in the TUI:

1. Select a profile and press `Enter` to load it
2. Toggle skills and plugins with `Space`
3. Press `w` to save those edits back to that profile
4. Or press `s` to save the working selection as a new profile

## Creating Your Own Profiles

Create an empty profile:

```bash
codex-prof profile create backend
```

Create a profile from whatever is currently active:

```bash
codex-prof profile create backend --from-current
```

Add or remove items later:

```bash
codex-prof profile add backend supabase --kind skill
codex-prof profile add backend github@openai-curated --kind plugin
codex-prof profile remove backend find-skills --kind skill
codex-prof profile delete backend
```

## Footprint Estimates

You can estimate the current skill and plugin footprint with:

```bash
codex-prof footprint
codex-prof footprint --show-files
```

The estimate counts discovered `SKILL.md` files for:

- active user-installed skills under `~/.agents/skills`
- enabled plugin skills under the Codex plugin cache

It reports bytes, lines, and a coarse estimated token count. This is an upper-bound style estimate, not an exact measurement of what Codex will send on every turn.

## Notes

- Skills are never deleted. They move between active and disabled directories.
- Plugin state is updated in `~/.codex/config.toml` by editing existing `[plugins."..."]` blocks.
- After a successful apply, start a new Codex session for changes to take effect.
