"""Construye el cubo Homologado+TTE sin recalcular porcentajes prematuramente."""

from __future__ import annotations

from typing import Any

from data_loader import BUSINESS_RULES, SCOPE, UNASSIGNED_PBP_LABEL, UNASSIGNED_PCD_LABEL, UNASSIGNED_SUPERVISOR_LABEL
from homologated_tte_enrichment_loader import TTE_UNMATCHED_LABEL
from processors import ATTRITION_METRIC_BY_SOURCE_TYPE, NUMERIC_METRIC_NAMES, resolve_dashboard_segment

REGIONAL_DIMENSION_CONTRACT = (
    ("tte_coverage_status", "tteCoverageStatus", TTE_UNMATCHED_LABEL),
    ("tte_campaign", "tteCampaign", TTE_UNMATCHED_LABEL),
    ("tte_director", "tteDirector", TTE_UNMATCHED_LABEL),
    ("tte_manager", "tteManager", TTE_UNMATCHED_LABEL),
    ("tte_n3", "tteN3", TTE_UNMATCHED_LABEL),
    ("tte_region", "tteRegion", TTE_UNMATCHED_LABEL),
    ("tte_tier4", "tteTier4", TTE_UNMATCHED_LABEL),
    ("tte_tier5", "tteTier5", TTE_UNMATCHED_LABEL),
    ("tte_tier6", "tteTier6", TTE_UNMATCHED_LABEL),
    ("tte_location", "tteLocation", TTE_UNMATCHED_LABEL),
    ("tte_role", "tteRole", TTE_UNMATCHED_LABEL),
    ("tte_seniority", "tteSeniority", TTE_UNMATCHED_LABEL),
    ("tte_historical_status", "tteHistoricalStatus", TTE_UNMATCHED_LABEL),
    ("tte_inss", "tteInss", TTE_UNMATCHED_LABEL),
)


def resolve_enriched_dashboard_segment(source_row: dict[str, Any]) -> str | None:
    """Conserva segmentos homologados y separa la ampliación regional.

    Una categoría adicional sólo es válida cuando el SQL confirmó cobertura TTE y
    ``Agrupador_1`` coincide exactamente con el Seniority regional.
    """

    source_group = str(source_row["source_group"])
    official_segment = resolve_dashboard_segment(source_group)
    if official_segment:
        return official_segment
    if (
        source_row.get("tte_coverage_status") == "Con cobertura TTE"
        and source_group == str(source_row.get("tte_seniority") or "")
    ):
        return "Otros Seniorities TTE"
    return None

def enriched_dimensions(source_row: dict[str, Any], segment: str) -> dict[str, Any]:
    """Normaliza dimensiones oficiales y regionales con nombres no ambiguos."""

    dimensions = {
        "year": int(source_row["year"]),
        "month": int(source_row["month"]),
        "segment": segment,
        "region": str(source_row.get("region") or "Sin especificar"),
        "operationType": str(source_row.get("operation_type") or "Sin especificar"),
        "siteOperativo": str(source_row.get("site_operativo") or "Sin especificar"),
        "area": str(source_row.get("area") or "Sin especificar"),
        "subarea": str(source_row.get("subarea") or "Sin especificar"),
        "pbp": str(source_row.get("pbp") or UNASSIGNED_PBP_LABEL),
        "pcd": str(source_row.get("pcd") or UNASSIGNED_PCD_LABEL),
        "supervisor": str(source_row.get("supervisor") or UNASSIGNED_SUPERVISOR_LABEL),
    }
    for source_name, published_name, fallback_label in REGIONAL_DIMENSION_CONTRACT:
        dimensions[published_name] = str(source_row.get(source_name) or fallback_label)
    return dimensions


def enriched_dimension_key(source_row: dict[str, Any], segment: str) -> tuple[Any, ...]:
    """Define el grano completo usado para combinar métricas de las dos fuentes oficiales."""

    dimensions = enriched_dimensions(source_row, segment)
    return tuple(dimensions.values())


def create_empty_enriched_cube_cell(source_row: dict[str, Any], segment: str) -> dict[str, Any]:
    """Inicializa una celda aditiva con todas las dimensiones publicadas."""

    return {
        **enriched_dimensions(source_row, segment),
        **{metric_name: 0.0 for metric_name in NUMERIC_METRIC_NAMES},
    }


def add_enriched_metric(cells_by_key: dict[tuple[Any, ...], dict[str, Any]], source_row: dict[str, Any], segment: str, metric_name: str, value: Any) -> None:
    """Suma una métrica oficial sin alterar su definición ni denominador."""

    cell_key = enriched_dimension_key(source_row, segment)
    cube_cell = cells_by_key.setdefault(cell_key, create_empty_enriched_cube_cell(source_row, segment))
    cube_cell[metric_name] += float(value or 0)


def add_enriched_attrition_metric(cells_by_key: dict[tuple[Any, ...], dict[str, Any]], source_row: dict[str, Any], segment: str) -> None:
    """Aplica exactamente la exclusión de bajas vigente en la vista homologada."""

    if source_row.get("attrition_type") == "No cuenta" and source_row.get("attrition_reason") == BUSINESS_RULES["excluded_unspecified_attrition_reason"]:
        return
    metric_name = ATTRITION_METRIC_BY_SOURCE_TYPE.get(str(source_row.get("attrition_type")))
    if metric_name:
        add_enriched_metric(cells_by_key, source_row, segment, metric_name, source_row["value"])


def compile_homologated_tte_enriched_cube(source_results_by_query_name: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Construye el cubo de prueba manteniendo NOMINA_ALL/HYPER_ABS como fuentes métricas."""

    cells_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for source_row in source_results_by_query_name.get("direct_headcount_and_attrition", []):
        segment = resolve_enriched_dashboard_segment(source_row)
        if not segment:
            continue
        if source_row["record_type"] in ("Headcount Historico", "Headcount Actual"):
            add_enriched_metric(cells_by_key, source_row, segment, "headcount", source_row["value"])
        elif source_row["record_type"] == "Bajas":
            add_enriched_attrition_metric(cells_by_key, source_row, segment)
    for source_row in source_results_by_query_name.get("direct_hirings", []):
        segment = resolve_enriched_dashboard_segment(source_row)
        if segment:
            add_enriched_metric(cells_by_key, source_row, segment, "hirings", source_row["value"])
    for source_row in source_results_by_query_name.get("external_headcount_and_attrition", []):
        if source_row["record_type"] in ("Headcount Historico", "Headcount Actual"):
            add_enriched_metric(cells_by_key, source_row, "Externos", "headcount", source_row["value"])
        elif source_row["record_type"] == "Bajas":
            add_enriched_attrition_metric(cells_by_key, source_row, "Externos")
    for source_row in source_results_by_query_name.get("absenteeism", []):
        segment = (
            "Externos"
            if str(source_row.get("external_employee")) == SCOPE["external_employee_flag"]
            else resolve_enriched_dashboard_segment(source_row)
        )
        if not segment:
            continue
        for source_metric_name, cube_metric_name in (
            ("scheduled_workforce", "scheduled_workforce"),
            ("manageable_absenteeism", "manageable_absenteeism"),
            ("non_manageable_absenteeism", "non_manageable_absenteeism"),
            ("other_absenteeism", "other_absenteeism"),
        ):
            add_enriched_metric(cells_by_key, source_row, segment, cube_metric_name, source_row[source_metric_name])
    return list(cells_by_key.values())


def compile_homologated_tte_enriched_reason_series(source_results_by_query_name: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Conserva motivos oficiales con las mismas dimensiones del cubo enriquecido."""

    reason_cells: list[dict[str, Any]] = []
    for query_name, external_segment in (("direct_headcount_and_attrition", None), ("external_headcount_and_attrition", "Externos")):
        for source_row in source_results_by_query_name.get(query_name, []):
            if source_row.get("record_type") != "Bajas":
                continue
            if source_row.get("attrition_type") == "No cuenta" and source_row.get("attrition_reason") == BUSINESS_RULES["excluded_unspecified_attrition_reason"]:
                continue
            segment = external_segment or resolve_enriched_dashboard_segment(source_row)
            if segment:
                reason_cells.append({
                    **enriched_dimensions(source_row, segment),
                    "family": "attrition",
                    "reason": str(source_row.get("attrition_reason") or "Sin especificar"),
                    "attritionType": str(source_row.get("attrition_type") or "Sin especificar"),
                    "value": float(source_row.get("value") or 0),
                })
    for source_row in source_results_by_query_name.get("absenteeism", []):
        segment = (
            "Externos"
            if str(source_row.get("external_employee")) == SCOPE["external_employee_flag"]
            else resolve_enriched_dashboard_segment(source_row)
        )
        if segment:
            reason_cells.append({
                **enriched_dimensions(source_row, segment),
                "family": "absence",
                "reason": str(source_row.get("absenteeism_reason") or "Sin especificar"),
                "manageable_absenteeism": float(source_row.get("manageable_absenteeism") or 0),
                "non_manageable_absenteeism": float(source_row.get("non_manageable_absenteeism") or 0),
                "other_absenteeism": float(source_row.get("other_absenteeism") or 0),
            })
    return reason_cells