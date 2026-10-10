from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PracticeConfig:
    path: Path
    workspace_root: Path
    scratch: Path
    tracker_database: Path
    document_template: Path
    document_author: str
    timezone: str
    jurisdiction_profile: str
    mail_adapter: str
    calendar_adapter: str
    practice_manager_adapter: str
    calendar_id: str
    mail_fixture: Path | None
    gmail_token_env: str
    gmail_imap_account_env: str
    gmail_imap_secret_env: str
    gmail_imap_keychain_service: str
    calendar_token_env: str
    calendar_api_base: str
    external_ai: bool
    branding_mode: str
    branding_label: str
    modules: dict[str, bool]


def _required(table: dict, key: str, section: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing [{section}].{key}")
    return value.strip()


def load_config(path: str | Path) -> PracticeConfig:
    config_path = Path(path).expanduser().resolve()
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)
    if raw.get("schema_version") != 1:
        raise ValueError("unsupported or missing schema_version")
    workspace = raw.get("workspace", {})
    tracker = raw.get("tracker", {})
    documents = raw.get("documents", {})
    jurisdiction = raw.get("jurisdiction", {})
    branding = raw.get("branding", {})
    modules_raw = raw.get("modules", {})
    integrations = raw.get("integrations", {})
    calendar = raw.get("calendar", {})
    review = raw.get("review", {})
    root = Path(_required(workspace, "root", "workspace")).expanduser().resolve()
    scratch = Path(_required(workspace, "scratch", "workspace")).expanduser().resolve()
    database = Path(_required(tracker, "database", "tracker")).expanduser().resolve()
    template = Path(_required(documents, "template", "documents")).expanduser().resolve()
    profile = jurisdiction.get("profile", "none")
    if profile not in {"none", "ontario"}:
        raise ValueError("jurisdiction profile must be 'none' or 'ontario'")
    branding_mode = str(branding.get("mode", "neutral"))
    if branding_mode not in {"neutral", "individual", "firm"}:
        raise ValueError("branding mode must be 'neutral', 'individual', or 'firm'")
    branding_label = str(branding.get("label", "Organization")).strip()
    if not branding_label:
        raise ValueError("branding label must not be blank")
    module_names = ("matter", "tracker", "letters", "redline", "calendar", "review")
    modules: dict[str, bool] = {}
    for name in module_names:
        value = modules_raw.get(name, True)
        if not isinstance(value, bool):
            raise ValueError(f"module {name} must be true or false")
        modules[name] = value
    if not modules["matter"] or not modules["tracker"]:
        raise ValueError("matter and tracker modules are required")
    external_ai = review.get("external_ai", False)
    if external_ai is not False:
        raise ValueError("the bundled review workflow requires review.external_ai = false")
    adapters = {
        "mail_adapter": str(integrations.get("mail_adapter", "unavailable")),
        "calendar_adapter": str(integrations.get("calendar_adapter", "unavailable")),
        "practice_manager_adapter": str(integrations.get("practice_manager_adapter", "unavailable")),
    }
    allowed = {
        "mail_adapter": {
            "unavailable", "fixture-json", "claude-gmail-connector", "codex-session-tools",
            "gmail-api-readonly",
            "gmail-imap-readonly",
        },
        "calendar_adapter": {"unavailable", "google-calendar-api"},
        "practice_manager_adapter": {"unavailable"},
    }
    for name, value in adapters.items():
        if value not in allowed[name]:
            raise ValueError(f"unsupported {name}: {value}")
    credentials = raw.get("credentials", {})
    mail_fixture_value = str(integrations.get("mail_fixture", "")).strip()
    mail_fixture = Path(mail_fixture_value).expanduser().resolve() if mail_fixture_value else None
    return PracticeConfig(
        path=config_path,
        workspace_root=root,
        scratch=scratch,
        tracker_database=database,
        document_template=template,
        document_author=str(documents.get("author", "Authorized reviewer")),
        timezone=str(workspace.get("timezone", "UTC")),
        jurisdiction_profile=profile,
        mail_adapter=adapters["mail_adapter"],
        calendar_adapter=adapters["calendar_adapter"],
        practice_manager_adapter=adapters["practice_manager_adapter"],
        calendar_id=str(calendar.get("calendar_id", "")),
        mail_fixture=mail_fixture,
        gmail_token_env=str(credentials.get("gmail_token_env", "LAWYEREDOS_GMAIL_TOKEN")),
        gmail_imap_account_env=str(
            credentials.get("gmail_imap_account_env", "LAWYEREDOS_GMAIL_IMAP_ACCOUNT")
        ),
        gmail_imap_secret_env=str(
            credentials.get("gmail_imap_secret_env", "LAWYEREDOS_GMAIL_IMAP_SECRET")
        ),
        gmail_imap_keychain_service=str(credentials.get("gmail_imap_keychain_service", "")).strip(),
        calendar_token_env=str(credentials.get("calendar_token_env", "LAWYEREDOS_CALENDAR_TOKEN")),
        calendar_api_base=str(calendar.get("api_base", "https://www.googleapis.com/calendar/v3")),
        external_ai=False,
        branding_mode=branding_mode,
        branding_label=branding_label,
        modules=modules,
    )
