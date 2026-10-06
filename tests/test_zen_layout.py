"""Layout and config of the full prototype: kb folders, offices, demo mailboxes, .env.example, docs, no secrets in git."""
import re
import subprocess

import pytest
import yaml

from retrieval.index_md import read_index
from zenai.config import ROOT, load_config
from zenai.offices import OfficeConfigError, handoff_office, load_mailboxes, load_offices, plus_address

FOLDERS = {"IT", "FINANCE", "ACADEMICS", "COURSE_SPECIFIC", "HOSTEL", "CAMPUS_SERVICES", "EMPLOYEES",
           "STUDENT_SUPPORT"}
OFFICES = FOLDERS - {"COURSE_SPECIFIC"} | {"HELPDESK"}


# ---- knowledge base folders ----

def test_kb_has_exactly_the_agreed_folders_each_with_an_index():
    found = {p.name for p in (ROOT / "kb").iterdir() if p.is_dir()}
    assert found == FOLDERS and not (ROOT / "kb" / "HELPDESK").exists()
    for folder in FOLDERS:
        assert isinstance(read_index(ROOT / "kb" / folder / "INDEX.md"), list)


def test_every_kb_file_is_listed_in_its_folder_index():
    for folder in FOLDERS:
        d = ROOT / "kb" / folder
        listed = {e["file"] for e in read_index(d / "INDEX.md")}
        for f in d.rglob("*"):
            if f.is_file() and f.name != "INDEX.md":
                assert f.relative_to(d).as_posix() in listed, f"kb/{folder}/{f.name} is not listed in INDEX.md"


def test_the_kb_validates_with_no_errors():
    from retrieval.kb import scan_kb

    scan = scan_kb(load_config())
    assert scan.errors == []
    assert scan.warnings == []  # nothing unlisted, missing or unknown is hiding in kb/


# ---- offices.yaml ----

def test_offices_and_folders():
    cfg = load_offices()
    assert set(cfg["folders"]) == FOLDERS and set(cfg["offices"]) == OFFICES
    assert "HELPDESK" not in cfg["folders"]
    assert {f: handoff_office(f, cfg) for f in FOLDERS} == {f: f for f in FOLDERS} | {"COURSE_SPECIFIC": "ACADEMICS"}
    assert "faculty" in cfg["folders"]["COURSE_SPECIFIC"]["note"]


def test_offices_channels_and_required_fields():
    offices = load_offices()["offices"]
    assert {o: c["handoff_channel"] for o, c in offices.items()} == \
        {o: "email" for o in OFFICES} | {"CAMPUS_SERVICES": "punctualiti"}
    assert offices["HOSTEL"]["required_fields"]["fix_or_complaint"] == ["hostel_block", "room_no", "issue"]
    assert offices["CAMPUS_SERVICES"]["required_fields"]["fix_or_complaint"] == ["location", "category", "description"]
    assert offices["CAMPUS_SERVICES"]["punctualiti_categories"]
    assert "TODO" in (ROOT / "config" / "offices.yaml").read_text(encoding="utf-8")


def test_office_config_errors(tmp_path):
    bad = tmp_path / "o.yaml"
    bad.write_text(yaml.safe_dump({"folders": {"X": {"handoff_office": "NOPE"}}, "offices": {}}), encoding="utf-8")
    with pytest.raises(OfficeConfigError, match="unknown office"):
        load_offices(bad)
    bad.write_text(yaml.safe_dump({"folders": {"HELPDESK": {"handoff_office": "HELPDESK"}},
                                   "offices": {"HELPDESK": {"handoff_channel": "email", "required_fields": {}}}}),
                   encoding="utf-8")
    with pytest.raises(OfficeConfigError, match="HELPDESK"):
        load_offices(bad)


# ---- demo mailboxes ----

def test_mailboxes_are_built_from_demo_gmail_with_plus_tags():
    boxes = load_mailboxes({"DEMO_GMAIL": "demo.user@gmail.com"})
    assert boxes["offices"] == {
        "IT": "demo.user+it@gmail.com", "FINANCE": "demo.user+finance@gmail.com",
        "ACADEMICS": "demo.user+academics@gmail.com", "HOSTEL": "demo.user+hostel@gmail.com",
        "CAMPUS_SERVICES": "demo.user+services@gmail.com", "EMPLOYEES": "demo.user+employees@gmail.com",
        "STUDENT_SUPPORT": "demo.user+studentsupport@gmail.com", "HELPDESK": "demo.user+helpdesk@gmail.com"}
    assert boxes["students"] == {"student1": "demo.user+student1@gmail.com", "student2": "demo.user+student2@gmail.com"}
    assert set(boxes["offices"]) == OFFICES


def test_mailbox_errors_and_no_address_in_the_yaml():
    with pytest.raises(OfficeConfigError, match="DEMO_GMAIL is not set"):
        load_mailboxes({})
    for bad in ("nobody", "@gmail.com", "a+b@example.test"):
        with pytest.raises(OfficeConfigError):
            plus_address(bad, "it")
    assert "@" not in (ROOT / "config" / "mailbox_map.yaml").read_text(encoding="utf-8").replace("# ", "").split(
        "\n", 3)[3]


# ---- .env.example and .gitignore ----

ENV_NAMES = """LLM_PROVIDER GEMINI_API_KEY AZURE_OPENAI_ENDPOINT AZURE_OPENAI_KEY AZURE_CHAT_DEPLOYMENT
AZURE_EMBED_DEPLOYMENT AZURE_SEARCH_ENDPOINT AZURE_SEARCH_ADMIN_KEY SEARCH_INDEX RETRIEVER EMAIL_PROVIDER ACS_CONNECTION_STRING
ACS_SENDER DEMO_GMAIL GMAIL_APP_PASSWORD APP_SECRET STAFF_PASSWORD_IT STAFF_PASSWORD_FINANCE
STAFF_PASSWORD_ACADEMICS STAFF_PASSWORD_HOSTEL STAFF_PASSWORD_CAMPUS_SERVICES STAFF_PASSWORD_EMPLOYEES
STAFF_PASSWORD_STUDENT_SUPPORT STAFF_PASSWORD_HELPDESK WEB_ORIGIN DEMO_MODE""".split()


def test_env_example_has_exactly_the_agreed_names_and_no_values():
    lines = [ln for ln in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    assert [ln.split("=")[0] for ln in lines] == ENV_NAMES
    assert all(ln.endswith("=") for ln in lines)


def test_runtime_state_dir_is_gitignored():
    assert ".data/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


# ---- docs ----

def test_policy_is_marked_as_team_defaults_and_covers_every_office():
    text = (ROOT / "POLICY.md").read_text(encoding="utf-8")
    assert "team defaults, 6 Oct 2026, confirm" in text
    for office in OFFICES:
        assert f"`{office}`" in text
    for intent in ("info", "fix_or_complaint", "course_specific", "no_owner", "safety", "out_of_scope"):
        assert f"`{intent}`" in text


def test_api_contract_lists_every_endpoint_and_stage():
    text = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
    endpoints = ["POST /api/chat", "GET /api/cases", "GET /api/cases/{case_id}", "POST /api/cases/{case_id}/approve",
                 "POST /api/cases/{case_id}/cancel", "POST /api/cases/{case_id}/punctualiti-ticket",
                 "POST /api/cases/{case_id}/confirm", "POST /api/cases/{case_id}/reopen", "POST /api/staff/login",
                 "POST /api/staff/logout", "GET /api/staff/queue", "GET /api/staff/cases/{case_id}",
                 "POST /api/staff/cases/{case_id}/stage", "POST /api/staff/cases/{case_id}/reply",
                 "POST /api/staff/cases/{case_id}/reassign", "GET /api/health", "GET /api/metrics"]
    for endpoint in endpoints:
        assert f"### `{endpoint}" in text, endpoint
    for stage in ("routed", "submitted", "seen", "in_progress", "resolved", "confirmed", "reopened", "cancelled"):
        assert f"`{stage}`" in text
    for action in ("answer", "not_found", "clarify", "handoff", "refuse", "safety"):
        assert f"`{action}`" in text


def test_claude_md_keeps_v1_rules_and_adds_the_new_ones():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for rule in ("Never use them to write prompts", "Never invent or hand-edit results",
                 "Every LLM and embedding call goes through the cached provider", "`.cache/`: LLM/embedding response cache",
                 "The LLM can never send email", "Demo students only", "Keys and passwords live only in `.env`",
                 "POLICY.md", "docs/API.md", "answers must cite" if False else "Answers must cite retrieved chunks"):
        assert rule in text, rule


# ---- no secrets in git ----

def _git(*args):
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    return out.stdout


def test_env_is_not_tracked_and_no_secret_value_appears_in_any_committable_file():
    files = [f for f in _git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0") if f]
    assert ".env" not in files
    env_path = ROOT / ".env"
    if not env_path.exists():
        pytest.skip("no local .env to compare against")
    secrets = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        value = value.strip()
        if sep and not name.startswith("#") and len(value) >= 8 and not value.startswith(("your_", "PASTE_", "http")):
            secrets[name.strip()] = value
    leaks = []
    for f in files:
        path = ROOT / f
        if path.suffix.lower() in (".png", ".pdf", ".jpg") or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        leaks += [f"{name} found in {f}" for name, value in secrets.items() if value in text]
    assert not leaks, "; ".join(leaks)  # names only: the values are never printed


def test_no_email_address_is_hardcoded_in_tracked_code_or_config():
    files = [f for f in _git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")
             if f.endswith((".py", ".yaml", ".yml", ".md", ".json", ".ts", ".tsx")) and not f.startswith(
                 ("results/", "data/", "kb/", "web/node_modules/"))]
    pattern = re.compile(r"[\w.+-]+@gmail\.com")
    allowed = {"name@gmail.com", "demo.user@gmail.com", "demo.user+it@gmail.com"}
    bad = []
    for f in files:
        for m in pattern.findall((ROOT / f).read_text(encoding="utf-8", errors="ignore")):
            if m not in allowed and not m.startswith(("demo.user+", "name+")):
                bad.append(f)
    assert not bad, f"gmail address in: {sorted(set(bad))}"
