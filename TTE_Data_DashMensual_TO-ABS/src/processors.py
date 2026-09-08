"""Transforma agregados oficiales en un cubo mensual filtrable por el navegador."""

from __future__ import annotations

from typing import Any

from data_loader import BUSINESS_RULES, SCOPE, UNASSIGNED_PBP_LABEL, UNASSIGNED_PCD_LABEL, UNASSIGNED_SUPERVISOR_LABEL

ATTRITION_METRIC_BY_SOURCE_TYPE = {"Renuncia": "resignations", "Despido": "dismissals", "Abandono de empleo": "abandonments", "No cuenta": "not_counted_attrition"}
NUMERIC_METRIC_NAMES = ("headcount", "hirings", "resignations", "dismissals", "abandonments", "not_counted_attrition", "scheduled_workforce", "manageable_absenteeism", "non_manageable_absenteeism", "other_absenteeism")


def resolve_dashboard_segment(source_group: str, is_external_employee: bool = False) -> str | None:
    """Mapea únicamente los segmentos oficialmente incluidos en Brasil."""
    if is_external_employee:
        return "Externos"
    for dashboard_segment, configured_source_group in SCOPE["direct_source_groups"].items():
        if source_group == configured_source_group:
            return dashboard_segment
    return None


def build_cube_cell_key(source_row: dict[str, Any], segment: str) -> tuple[Any, ...]:
    """Define el grano publicado: mes × segmento × Región × Tipo de operación."""
    return (int(source_row["year"]), int(source_row["month"]), segment, str(source_row.get("region") or "Sin especificar"), str(source_row.get("operation_type") or "Sin especificar"), str(source_row.get("site_operativo") or "Sin especificar"), str(source_row.get("area") or "Sin especificar"), str(source_row.get("subarea") or "Sin especificar"), str(source_row.get("pbp") or UNASSIGNED_PBP_LABEL), str(source_row.get("pcd") or UNASSIGNED_PCD_LABEL), str(source_row.get("supervisor") or UNASSIGNED_SUPERVISOR_LABEL))


def create_empty_cube_cell(dimension_key: tuple[Any, ...]) -> dict[str, Any]:
    """Inicializa todas las métricas aditivas, evitando nulos en el HTML."""
    year, month, segment, region, operation_type, site_operativo, area, subarea, pbp, pcd, supervisor = dimension_key
    return {"year": year, "month": month, "segment": segment, "region": region, "operationType": operation_type, "siteOperativo": site_operativo, "area": area, "subarea": subarea, "pbp": pbp, "pcd": pcd, "supervisor": supervisor, **{metric_name: 0.0 for metric_name in NUMERIC_METRIC_NAMES}}


def add_metric(cells_by_key: dict[tuple[Any, ...], dict[str, Any]], source_row: dict[str, Any], segment: str, metric_name: str, value: Any) -> None:
    """Suma una métrica fuente a una celda homogénea del cubo."""
    dimension_key = build_cube_cell_key(source_row, segment)
    cube_cell = cells_by_key.setdefault(dimension_key, create_empty_cube_cell(dimension_key))
    cube_cell[metric_name] += float(value or 0)


def add_attrition_metric(cells_by_key: dict[tuple[Any, ...], dict[str, Any]], source_row: dict[str, Any], segment: str) -> None:
    """Agrega bajas válidas; 'No cuenta/Sin Especificar' se excluye por regla vigente."""
    if source_row.get("attrition_type") == "No cuenta" and source_row.get("attrition_reason") == BUSINESS_RULES["excluded_unspecified_attrition_reason"]:
        return
    metric_name = ATTRITION_METRIC_BY_SOURCE_TYPE.get(str(source_row.get("attrition_type")))
    if metric_name:
        add_metric(cells_by_key, source_row, segment, metric_name, source_row["value"])




def compile_monthly_reason_series(source_results_by_query_name: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Conserva los motivos mensuales para las gráficas de detalle del navegador."""
    reason_cells: list[dict[str, Any]] = []

    def dimensions(source_row: dict[str, Any], segment: str) -> dict[str, Any]:
        return {"year": int(source_row["year"]), "month": int(source_row["month"]), "segment": segment, "region": str(source_row.get("region") or "Sin especificar"), "operationType": str(source_row.get("operation_type") or "Sin especificar"), "siteOperativo": str(source_row.get("site_operativo") or "Sin especificar"), "area": str(source_row.get("area") or "Sin especificar"), "subarea": str(source_row.get("subarea") or "Sin especificar"), "pbp": str(source_row.get("pbp") or UNASSIGNED_PBP_LABEL), "pcd": str(source_row.get("pcd") or UNASSIGNED_PCD_LABEL), "supervisor": str(source_row.get("supervisor") or UNASSIGNED_SUPERVISOR_LABEL)}

    def add_attrition_reason(source_row: dict[str, Any], segment: str) -> None:
        if source_row.get("attrition_type") == "No cuenta" and source_row.get("attrition_reason") == BUSINESS_RULES["excluded_unspecified_attrition_reason"]:
            return
        reason_cells.append({**dimensions(source_row, segment), "family": "attrition", "reason": str(source_row.get("attrition_reason") or "Sin especificar"), "attritionType": str(source_row.get("attrition_type") or "Sin especificar"), "value": float(source_row.get("value") or 0)})

    for source_row in source_results_by_query_name.get("direct_headcount_and_attrition", []):
        segment = resolve_dashboard_segment(str(source_row["source_group"]))
        if segment and source_row.get("record_type") == "Bajas":
            add_attrition_reason(source_row, segment)
    for source_row in source_results_by_query_name.get("external_headcount_and_attrition", []):
        if source_row.get("record_type") == "Bajas":
            add_attrition_reason(source_row, "Externos")
    for source_row in source_results_by_query_name.get("absenteeism", []):
        segment = resolve_dashboard_segment(str(source_row["source_group"]), str(source_row.get("external_employee")) == SCOPE["external_employee_flag"])
        if segment:
            reason_cells.append({**dimensions(source_row, segment), "family": "absence", "reason": str(source_row.get("absenteeism_reason") or "Sin especificar"), "manageable_absenteeism": float(source_row.get("manageable_absenteeism") or 0), "non_manageable_absenteeism": float(source_row.get("non_manageable_absenteeism") or 0), "other_absenteeism": float(source_row.get("other_absenteeism") or 0)})
    return reason_cells

def compile_monthly_dashboard_cube(source_results_by_query_name: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Construye el contrato del HTML sin calcular porcentajes prematuramente."""
    cells_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for source_row in source_results_by_query_name.get("direct_headcount_and_attrition", []):
        segment = resolve_dashboard_segment(str(source_row["source_group"]))
        if not segment:
            continue
        if source_row["record_type"] in ("Headcount Historico", "Headcount Actual"):
            add_metric(cells_by_key, source_row, segment, "headcount", source_row["value"])
        elif source_row["record_type"] == "Bajas":
            add_attrition_metric(cells_by_key, source_row, segment)
    for source_row in source_results_by_query_name.get("direct_hirings", []):
        segment = resolve_dashboard_segment(str(source_row["source_group"]))
        if segment:
            add_metric(cells_by_key, source_row, segment, "hirings", source_row["value"])
    for source_row in source_results_by_query_name.get("external_headcount_and_attrition", []):
        if source_row["record_type"] in ("Headcount Historico", "Headcount Actual"):
            add_metric(cells_by_key, source_row, "Externos", "headcount", source_row["value"])
        elif source_row["record_type"] == "Bajas":
            add_attrition_metric(cells_by_key, source_row, "Externos")
    for source_row in source_results_by_query_name.get("absenteeism", []):
        segment = resolve_dashboard_segment(str(source_row["source_group"]), str(source_row.get("external_employee")) == SCOPE["external_employee_flag"])
        if not segment:
            continue
        for source_metric_name, cube_metric_name in (("scheduled_workforce", "scheduled_workforce"), ("manageable_absenteeism", "manageable_absenteeism"), ("non_manageable_absenteeism", "non_manageable_absenteeism"), ("other_absenteeism", "other_absenteeism")):
            add_metric(cells_by_key, source_row, segment, cube_metric_name, source_row[source_metric_name])
    return sorted(cells_by_key.values(), key=lambda cell: (cell["year"], cell["month"], cell["segment"], cell["region"], cell["operationType"], cell["siteOperativo"], cell["area"], cell["subarea"], cell["pbp"], cell["pcd"], cell["supervisor"]))
