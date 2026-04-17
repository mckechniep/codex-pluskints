from __future__ import annotations

from .models import AppConfig, Profile


def get_profile(config: AppConfig, name: str) -> Profile:
    try:
        return config.profiles[name]
    except KeyError as exc:
        raise KeyError(f"unknown profile: {name}") from exc


def expand_profile_skills(profile: Profile, known_skills: set[str]) -> set[str]:
    if "*" in profile.enabled_skills:
        return set(known_skills)
    return set(profile.enabled_skills)


def expand_profile_plugins(profile: Profile, known_plugins: set[str]) -> set[str]:
    if "*" in profile.enabled_plugins:
        return set(known_plugins)
    return set(profile.enabled_plugins)


def save_profile(
    config: AppConfig,
    name: str,
    enabled_skills: set[str],
    enabled_plugins: set[str],
) -> Profile:
    profile = Profile(
        name=name,
        enabled_skills=sorted(enabled_skills),
        enabled_plugins=sorted(enabled_plugins),
    )
    config.profiles[name] = profile
    return profile


def create_profile(
    config: AppConfig,
    name: str,
    enabled_skills: set[str] | None = None,
    enabled_plugins: set[str] | None = None,
    overwrite: bool = False,
) -> Profile:
    if name in config.profiles and not overwrite:
        raise ValueError(f"profile already exists: {name}")
    return save_profile(
        config,
        name,
        enabled_skills=enabled_skills or set(),
        enabled_plugins=enabled_plugins or set(),
    )


def delete_profile(config: AppConfig, name: str) -> Profile:
    try:
        return config.profiles.pop(name)
    except KeyError as exc:
        raise KeyError(f"unknown profile: {name}") from exc


def update_profile_items(
    profile: Profile,
    *,
    skills: set[str] | None = None,
    plugins: set[str] | None = None,
) -> Profile:
    if skills is not None:
        profile.enabled_skills = sorted(skills)
    if plugins is not None:
        profile.enabled_plugins = sorted(plugins)
    return profile
