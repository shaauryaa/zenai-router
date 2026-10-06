"""Load config/offices.yaml and config/mailbox_map.yaml. POLICY.md is the source of truth for both files.

Demo mailbox addresses are built here from DEMO_GMAIL (in .env) with plus tags, so the Gmail address is
never stored in git.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from .config import ROOT

CONFIG = ROOT / "config"
KB = ROOT / "kb"


class OfficeConfigError(ValueError):
    pass


def _yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_offices(path: Path = CONFIG / "offices.yaml") -> dict:
    """The offices.yaml content, checked: every folder hands off to a real office, HELPDESK has no folder,
    and every office has a channel and required_fields."""
    cfg = _yaml(path)
    folders, offices = cfg["folders"], cfg["offices"]
    for name, folder in folders.items():
        if folder["handoff_office"] not in offices:
            raise OfficeConfigError(f"folder {name} hands off to unknown office {folder['handoff_office']}")
    if "HELPDESK" in folders:
        raise OfficeConfigError("HELPDESK holds no documents, so it must not be a folder")
    for name, office in offices.items():
        if office.get("handoff_channel") not in ("email", "punctualiti"):
            raise OfficeConfigError(f"office {name} needs handoff_channel email or punctualiti")
        if not isinstance(office.get("required_fields"), dict):
            raise OfficeConfigError(f"office {name} needs required_fields")
    return cfg


def plus_address(gmail: str, tag: str) -> str:
    local, sep, domain = gmail.strip().partition("@")
    if not local or not sep or not domain or "+" in local:
        raise OfficeConfigError("DEMO_GMAIL must be a plain address like name@gmail.com")
    return f"{local}+{tag}@{domain}"


def load_mailboxes(env=None, path: Path = CONFIG / "mailbox_map.yaml") -> dict:
    """{'offices': {OFFICE: address}, 'students': {student_id: address}} built from DEMO_GMAIL."""
    env = os.environ if env is None else env
    gmail = env.get("DEMO_GMAIL")
    if not gmail:
        raise OfficeConfigError("DEMO_GMAIL is not set; add it to .env")
    cfg = _yaml(path)
    return {kind: {name: plus_address(gmail, tag) for name, tag in cfg[kind].items()}
            for kind in ("offices", "students")}


def handoff_office(folder: str, offices_cfg: dict | None = None) -> str:
    """Office that receives a handoff for a topic found in this knowledge folder."""
    return (offices_cfg or load_offices())["folders"][folder]["handoff_office"]
