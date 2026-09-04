"""Serializa el cubo oficial en un único HTML portable."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_loader import DASHBOARD_CONFIGURATION

HTML_TEMPLATE_PATH = Path(__file__).resolve().parent / "template_dashboard.html"


def write_dashboard_html(monthly_cube_cells: list[dict[str, Any]], output_html_path: Path, reporting_year: int, last_calendar_month: int) -> None:
    """Inserta sólo datos agregados y configuración visual necesaria para el navegador."""
    dashboard_payload = {
        "title": DASHBOARD_CONFIGURATION["dashboard"]["title"],
        "subtitle": DASHBOARD_CONFIGURATION["dashboard"]["subtitle"],
        "country": DASHBOARD_CONFIGURATION["scope"]["country"],
        "reportingYear": reporting_year,
        "lastCalendarMonth": last_calendar_month,
        "segments": ["Total", "Determinado (CDBR)", "Indeterminado", "Externos"],
        "cells": monthly_cube_cells,
    }
    serialized_payload = json.dumps(dashboard_payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template_contents = HTML_TEMPLATE_PATH.read_text(encoding="utf-8")
    output_html_path.write_text(template_contents.replace("/* DASHBOARD_DATA_PLACEHOLDER */", f"window.DASHBOARD_DATA = {serialized_payload};"), encoding="utf-8")
