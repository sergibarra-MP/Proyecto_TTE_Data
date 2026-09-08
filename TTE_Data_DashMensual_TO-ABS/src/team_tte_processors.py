"""Convierte la extracción regional al contrato explícito de la pestaña Team TTE."""

from __future__ import annotations

from typing import Any

from data_loader import DASHBOARD_CONFIGURATION

REGIONAL_NUMERIC_FIELDS = (
    "scheduled_population",
    "manageable_absence",
    "non_manageable_absence",
    "other_absence",
    "monthly_headcount_indicator",
    "is_in_average_headcount_snapshot",
    "total_turnover",
    "resignations",
    "dismissals",
    "not_counted_turnover",
    "turnover_target",
    "job_abandonments",
    "reason_illness",
    "reason_unjustified_absence",
    "reason_leader_permission",
    "reason_medical_service_permission",
    "reason_suspension_sanction",
)


def compile_team_tte_dashboard_payload(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Publica nombres claros y tipos JSON estables, sin calcular tasas en Python."""

    source_minimum_date = min(
        (str(source_row.get("source_minimum_date") or "9999-12-31") for source_row in source_rows),
        default="",
    )
    source_maximum_date = max(
        (str(source_row.get("source_maximum_date") or "") for source_row in source_rows),
        default="",
    )
    person_month_cells: list[dict[str, Any]] = []
    for source_row in source_rows:
        person_month_cells.append(
            {
                "year": int(source_row["year"]),
                "month": int(source_row["month"]),
                "consumerId": str(source_row["consumer_id"]),
                "peopleBusinessPartner": str(source_row["people_business_partner"]),
                "campaign": str(source_row["campaign"]),
                "director": str(source_row["director"]),
                "manager": str(source_row["manager"]),
                "n3": str(source_row["n3"]),
                "tier4": str(source_row["tier4"]),
                "tier5": str(source_row["tier5"]),
                "tier6": str(source_row["tier6"]),
                "region": str(source_row["region"]),
                "location": str(source_row["location"]),
                "area": str(source_row["area"]),
                "subarea": str(source_row["subarea"]),
                "role": str(source_row["role"]),
                "seniority": str(source_row["seniority"]),
                "historicalStatus": str(source_row["historical_status"]),
                "pcd": str(source_row["pcd"]),
                "inss": str(source_row["inss"]),
                **{
                    numeric_field_name: float(source_row.get(numeric_field_name) or 0)
                    for numeric_field_name in REGIONAL_NUMERIC_FIELDS
                },
            }
        )

    return {
        "sourceTable": DASHBOARD_CONFIGURATION["bigquery"]["tables"]["team_tte_regional_base"],
        "sourceMinimumDate": source_minimum_date,
        "sourceMaximumDate": source_maximum_date,
        "initialSeniorityValues": DASHBOARD_CONFIGURATION["team_tte"]["initial_seniority_values"],
        "initialHistoricalStatusValues": DASHBOARD_CONFIGURATION["team_tte"]["initial_historical_status_values"],
        "cells": person_month_cells,
    }