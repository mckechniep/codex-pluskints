from __future__ import annotations

import json
from pathlib import Path

from .models import AppConfig, Profile

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "codex-profile-manager" / "config.json"


def default_config() -> AppConfig:
    home = Path.home()
    return AppConfig(
        skills_dir=home / ".agents" / "skills",
        disabled_dir=home / ".agents" / "skills.disabled",
        skill_lock_path=home / ".agents" / ".skill-lock.json",
        codex_config_path=home / ".codex" / "config.toml",
        profiles={
            "minimal": Profile(
                name="minimal",
                enabled_skills=["find-skills"],
                enabled_plugins=[],
            ),
            "coding": Profile(
                name="coding",
                enabled_skills=["supabase", "supabase-postgres-best-practices"],
                enabled_plugins=[
                    "github@openai-curated",
                    "build-web-apps@openai-curated",
                    "vercel@openai-curated",
                ],
            ),
            "full": Profile(name="full", enabled_skills=["*"], enabled_plugins=["*"]),
        },
    )


def config_to_dict(config: AppConfig) -> dict[str, object]:
    return {
        "skills_dir": str(config.skills_dir),
        "disabled_dir": str(config.disabled_dir),
        "skill_lock_path": str(config.skill_lock_path),
        "codex_config_path": str(config.codex_config_path),
        "profiles": {
            name: {
                "enabled_skills": profile.enabled_skills,
                "enabled_plugins": profile.enabled_plugins,
            }
            for name, profile in sorted(config.profiles.items())
        },
    }


def config_from_dict(payload: dict[str, object]) -> AppConfig:
    profiles_raw = payload.get("profiles", {})
    profiles: dict[str, Profile] = {}
    if isinstance(profiles_raw, dict):
        for name, value in profiles_raw.items():
            if not isinstance(value, dict):
                continue
            profiles[name] = Profile(
                name=name,
                enabled_skills=list(value.get("enabled_skills", [])),
                enabled_plugins=list(value.get("enabled_plugins", [])),
            )
    return AppConfig(
        skills_dir=Path(str(payload["skills_dir"])),
        disabled_dir=Path(str(payload["disabled_dir"])),
        skill_lock_path=Path(str(payload["skill_lock_path"])),
        codex_config_path=Path(str(payload["codex_config_path"])),
        profiles=profiles,
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def load_config(config_path: Path | None = None) -> tuple[AppConfig, Path]:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        config = default_config()
        save_config(config, path)
        return config, path
    payload = json.loads(path.read_text(encoding="utf-8"))
    return config_from_dict(payload), path


def save_config(config: AppConfig, config_path: Path | None = None) -> Path:
    path = config_path or DEFAULT_CONFIG_PATH
    serialized = json.dumps(config_to_dict(config), indent=2, sort_keys=True)
    _atomic_write(path, serialized + "\n")
    return path
