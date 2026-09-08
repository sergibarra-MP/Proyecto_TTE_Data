"""Serializa las tres vistas del dashboard en un único HTML portable."""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path
from typing import Any

from data_loader import DASHBOARD_CONFIGURATION

HTML_TEMPLATE_PATH = Path(__file__).resolve().parent / "template_dashboard.html"


def compress_payload_as_base64(payload: dict[str, Any]) -> str:
    """Serializa y comprime un payload sin mezclarlo con las demás vistas."""

    serialized_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    compressed_payload = gzip.compress(serialized_payload.encode("utf-8"), compresslevel=9)
    return base64.b64encode(compressed_payload).decode("ascii")


def write_dashboard_html(
    monthly_cube_cells: list[dict[str, Any]],
    reason_cells: list[dict[str, Any]],
    team_tte_payload: dict[str, Any],
    homologated_tte_enriched_cube_cells: list[dict[str, Any]],
    homologated_tte_enriched_reason_cells: list[dict[str, Any]],
    output_html_path: Path,
    reporting_year: int,
    last_calendar_month: int,
) -> None:
    """Inserta tres contratos de datos independientes en el mismo HTML."""

    homologated_dashboard_payload = {
        "title": DASHBOARD_CONFIGURATION["dashboard"]["title"],
        "subtitle": DASHBOARD_CONFIGURATION["dashboard"]["subtitle"],
        "country": DASHBOARD_CONFIGURATION["scope"]["country"],
        "reportingYear": reporting_year,
        "lastCalendarMonth": last_calendar_month,
        "segments": ["Total", "Determinado (CDBR)", "Indeterminado", "Externos"],
        "cells": monthly_cube_cells,
        "reasonCells": reason_cells,
    }
    regional_dashboard_payload = {
        "reportingYear": reporting_year,
        "lastCalendarMonth": last_calendar_month,
        **team_tte_payload,
    }
    homologated_tte_enriched_payload = {
        **homologated_dashboard_payload,
        "cells": homologated_tte_enriched_cube_cells,
        "reasonCells": homologated_tte_enriched_reason_cells,
        "enrichmentSource": "meli-people.SILVER_PE_SHIPPING.TTE_BRASIL_TABELA_BASE_PEOPLEBUSINESSPARTNER",
        "unmatchedLabel": "Sin cobertura TTE",
    }
    embedded_payload_javascript = "\n".join(
        [
            f'window.HOMOLOGATED_DASHBOARD_DATA_GZIP_BASE64 = "{compress_payload_as_base64(homologated_dashboard_payload)}";',
            f'window.TEAM_TTE_DASHBOARD_DATA_GZIP_BASE64 = "{compress_payload_as_base64(regional_dashboard_payload)}";',
            f'window.HOMOLOGATED_TTE_DASHBOARD_DATA_GZIP_BASE64 = "{compress_payload_as_base64(homologated_tte_enriched_payload)}";',
        ]
    )
    template_contents = HTML_TEMPLATE_PATH.read_text(encoding="utf-8")
    output_html_path.write_text(
        template_contents.replace("/* DASHBOARD_DATA_PLACEHOLDER */", embedded_payload_javascript),
        encoding="utf-8",
    )