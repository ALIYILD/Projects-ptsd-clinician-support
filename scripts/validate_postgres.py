from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Sequence

from ptsd_support.db.adapter import DatabaseSettings, connect, fetch_scalar
from ptsd_support.db.migrations import run_migrations


@dataclass(frozen=True)
class ValidationStep:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    settings: DatabaseSettings
    steps: list[ValidationStep]


def resolve_settings(dsn: str | None = None) -> DatabaseSettings:
    settings = DatabaseSettings.from_target()
    if dsn:
        return DatabaseSettings(engine="postgres", postgres_dsn=dsn)
    return settings


def validate_configuration(settings: DatabaseSettings) -> ValidationStep:
    if settings.engine != "postgres":
        return ValidationStep(
            name="config",
            ok=False,
            detail=(
                "Resolved database engine is not postgres. "
                "Set PTSD_SUPPORT_DB_ENGINE=postgres or pass --dsn."
            ),
        )
    if not settings.postgres_dsn:
        return ValidationStep(
            name="config",
            ok=False,
            detail=(
                "Postgres DSN is missing. "
                "Set PTSD_SUPPORT_POSTGRES_DSN or pass --dsn."
            ),
        )
    return ValidationStep(name="config", ok=True, detail="Postgres engine and DSN are configured.")


def _connect_probe(settings: DatabaseSettings) -> ValidationStep:
    conn = connect(settings)
    try:
        return ValidationStep(name="connect", ok=True, detail="Connected to Postgres successfully.")
    finally:
        conn.close()


def _health_probe(settings: DatabaseSettings) -> list[ValidationStep]:
    conn = connect(settings)
    try:
        server_version = fetch_scalar(conn, "SELECT version()")
        health_value = fetch_scalar(conn, "SELECT 1 AS ok")
    finally:
        conn.close()

    return [
        ValidationStep(
            name="health",
            ok=health_value == 1,
            detail=f"Health query returned {health_value!r}.",
        ),
        ValidationStep(
            name="server_version",
            ok=bool(server_version),
            detail=str(server_version or "No server version returned."),
        ),
    ]


def validate_postgres(settings: DatabaseSettings) -> ValidationReport:
    steps: list[ValidationStep] = []

    config_step = validate_configuration(settings)
    steps.append(config_step)
    if not config_step.ok:
        return ValidationReport(ok=False, settings=settings, steps=steps)

    try:
        steps.append(_connect_probe(settings))
    except Exception as exc:
        steps.append(ValidationStep(name="connect", ok=False, detail=f"{type(exc).__name__}: {exc}"))
        return ValidationReport(ok=False, settings=settings, steps=steps)

    try:
        run_migrations(settings)
        steps.append(ValidationStep(name="migrations", ok=True, detail="Migrations completed successfully."))
    except Exception as exc:
        steps.append(ValidationStep(name="migrations", ok=False, detail=f"{type(exc).__name__}: {exc}"))
        return ValidationReport(ok=False, settings=settings, steps=steps)

    try:
        steps.extend(_health_probe(settings))
    except Exception as exc:
        steps.append(ValidationStep(name="health", ok=False, detail=f"{type(exc).__name__}: {exc}"))
        return ValidationReport(ok=False, settings=settings, steps=steps)

    return ValidationReport(ok=all(step.ok for step in steps), settings=settings, steps=steps)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the configured Postgres runtime.")
    parser.add_argument(
        "--dsn",
        help="Optional Postgres DSN override. If provided, validation runs against this DSN.",
    )
    return parser


def format_report(report: ValidationReport) -> str:
    lines = [
        f"engine={report.settings.engine}",
        f"dsn={'set' if report.settings.postgres_dsn else 'missing'}",
    ]
    for step in report.steps:
        status = "OK" if step.ok else "ERROR"
        lines.append(f"[{status}] {step.name}: {step.detail}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = resolve_settings(dsn=args.dsn)
    report = validate_postgres(settings)
    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
