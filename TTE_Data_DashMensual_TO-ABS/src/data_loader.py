"""Carga agregados oficiales de BigQuery para el dashboard TTE Brasil.

Esta capa conoce tablas y SQL; no calcula tasas ni genera interfaz. Las consultas
se mantienen al grano mensual y con dimensiones que la primera versión publica.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT_DIRECTORY = Path(__file__).resolve().parent.parent
CONFIGURATION_FILE_PATH = PROJECT_ROOT_DIRECTORY / "config" / "dashboard_config.json"


def load_dashboard_configuration() -> dict[str, Any]:
    """Carga la única fuente de verdad de tablas, alcance y reglas editables."""

    return json.loads(CONFIGURATION_FILE_PATH.read_text(encoding="utf-8"))


DASHBOARD_CONFIGURATION = load_dashboard_configuration()
TABLES = DASHBOARD_CONFIGURATION["bigquery"]["tables"]
SCOPE = DASHBOARD_CONFIGURATION["scope"]
BUSINESS_RULES = DASHBOARD_CONFIGURATION["business_rules"]
UNASSIGNED_PBP_LABEL = BUSINESS_RULES["unassigned_pbp_label"]
# Límite preventivo de lectura por consulta (aprox. USD 1).
MAXIMUM_BYTES_BILLED_PER_QUERY = 160 * 1024 * 1024 * 1024


def build_official_source_queries() -> dict[str, str]:
    """Devuelve SQL parametrizado; ningún filtro de interfaz se interpola en SQL."""

    location_join_for_workforce = f"""LEFT JOIN `{TABLES['location_catalog']}` AS location_catalog
  ON source.Pais_Region = location_catalog.Pais_Region
 AND UPPER(TRIM(source.Ubicacion__Nombre)) = UPPER(TRIM(location_catalog.Ubicacion__Nombre))"""
    location_join_for_absenteeism = f"""LEFT JOIN `{TABLES['location_catalog']}` AS location_catalog
  ON source.Pais_region = location_catalog.Pais_Region
 AND UPPER(TRIM(source.ubicacion)) = UPPER(TRIM(location_catalog.Ubicacion__Nombre))"""

    common_month_window = "source.Ano = @reporting_year AND source.Mes BETWEEN 1 AND @last_calendar_month"
    return {
        "direct_headcount_and_attrition": f"""SELECT
  source.Ano AS year, source.Mes AS month, source.Agrupador_1 AS source_group,
  UPPER(TRIM(source.Ubicacion__Nombre)) AS site_operativo, source.Area AS area, source.Subarea AS subarea, COALESCE(NULLIF(UPPER(TRIM(source.People_Business_Partner__People_BP_Supervisores_Adicionales_Nombre)), ''), @unassigned_pbp_label) AS pbp, location_catalog.Region AS region,
  location_catalog.Site AS operation_type,
  source.Tipo AS record_type, source.tipoBaja AS attrition_type,
  source.motivosDeSalida AS attrition_reason,
  COUNT(DISTINCT source.ID_de_usuario_empleado) AS value
FROM `{TABLES['workforce_and_attrition']}` AS source
{location_join_for_workforce}
WHERE {common_month_window}
  AND source.Pais_Region = @country_name
  AND source.Agrupador_1 IN UNNEST(@direct_source_groups)
  AND source.Tipo IN ('Headcount Historico', 'Headcount Actual', 'Bajas')
  AND UPPER(TRIM(source.Ubicacion__Nombre)) NOT IN UNNEST(@excluded_location_names)
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12""",
        "direct_hirings": f"""SELECT
  EXTRACT(YEAR FROM source.Datos_Laborales_Fecha_de_contratacion) AS year,
  EXTRACT(MONTH FROM source.Datos_Laborales_Fecha_de_contratacion) AS month,
  source.Agrupador_1 AS source_group, UPPER(TRIM(source.Ubicacion__Nombre)) AS site_operativo, source.Area AS area, source.Subarea AS subarea, COALESCE(NULLIF(UPPER(TRIM(source.People_Business_Partner__People_BP_Supervisores_Adicionales_Nombre)), ''), @unassigned_pbp_label) AS pbp,
  location_catalog.Region AS region, location_catalog.Site AS operation_type,
  COUNT(DISTINCT source.ID_de_usuario_empleado) AS value
FROM `{TABLES['workforce_and_attrition']}` AS source
{location_join_for_workforce}
WHERE source.Pais_Region = @country_name
  AND source.Agrupador_1 IN UNNEST(@direct_source_groups)
  AND EXTRACT(YEAR FROM source.Datos_Laborales_Fecha_de_contratacion) = @reporting_year
  AND EXTRACT(MONTH FROM source.Datos_Laborales_Fecha_de_contratacion) BETWEEN 1 AND @last_calendar_month
  AND UPPER(TRIM(source.Ubicacion__Nombre)) NOT IN UNNEST(@excluded_location_names)
GROUP BY 1,2,3,4,5,6,7,8,9""",
        "external_headcount_and_attrition": f"""SELECT
  source.Ano AS year, source.Mes AS month, UPPER(TRIM(source.Ubicacion__Nombre)) AS site_operativo, source.Area AS area, source.Subarea AS subarea, COALESCE(NULLIF(UPPER(TRIM(source.People_Business_Partner__People_BP_Supervisores_Adicionales_Nombre)), ''), @unassigned_pbp_label) AS pbp,
  location_catalog.Region AS region, location_catalog.Site AS operation_type, source.Tipo AS record_type,
  source.tipoBaja AS attrition_type, source.motivosDeSalida AS attrition_reason,
  COUNT(*) AS value
FROM `{TABLES['workforce_and_attrition']}` AS source
{location_join_for_workforce}
WHERE {common_month_window}
  AND source.Pais_Region = @country_name
  AND source.Agrupador_1 = @external_source_group
  AND source.Tipo IN ('Headcount Historico', 'Headcount Actual', 'Bajas')
  AND UPPER(TRIM(source.Ubicacion__Nombre)) NOT IN UNNEST(@excluded_location_names)
GROUP BY 1,2,3,4,5,6,7,8,9,10,11""",
        "absenteeism": f"""SELECT
  source.Ano AS year, source.Mes AS month, source.Agrupador_1 AS source_group,
  source.colaborador_externo AS external_employee, UPPER(TRIM(source.ubicacion)) AS site_operativo, source.Area AS area, source.Subarea AS subarea, COALESCE(NULLIF(UPPER(TRIM(source.Pbp)), ''), @unassigned_pbp_label) AS pbp,
  location_catalog.Region AS region, CASE WHEN source.CAT_TA = 'No MAP' AND UPPER(TRIM(source.ubicacion)) IN ('BRES01', 'BRPR01') THEN 'Full'
       ELSE source.CAT_TA END AS operation_type,
  source.Motivo_ausentismo AS absenteeism_reason,
  SUM(source.Dotacion_programada) AS scheduled_workforce,
  SUM(source.Ausentismo_gestionable) AS manageable_absenteeism,
  SUM(source.Ausentismo_No_Gestionable) AS non_manageable_absenteeism,
  SUM(source.Ausentismo_otros) AS other_absenteeism
FROM `{TABLES['official_absenteeism']}` AS source
{location_join_for_absenteeism}
WHERE {common_month_window}
  AND source.Pais_region = @country_name
  AND source.Motivo_ausentismo != @excluded_absenteeism_reason
  AND source.CAT_TA NOT IN UNNEST(@excluded_operational_categories)
  AND UPPER(TRIM(source.ubicacion)) NOT IN UNNEST(@excluded_location_names)
  AND (source.colaborador_externo = @external_employee_flag OR source.Agrupador_1 IN UNNEST(@direct_source_groups))
GROUP BY 1,2,3,4,5,6,7,8,9,10,11""",
    }


def load_source_results_from_bigquery(reporting_year: int, last_calendar_month: int) -> dict[str, list[dict[str, Any]]]:
    """Ejecuta las consultas oficiales con parámetros tipados y auditables."""

    try:
        from google.cloud import bigquery
    except ImportError as import_error:
        raise RuntimeError("Falta google-cloud-bigquery. Ejecuta pip install -r requirements.txt") from import_error

    client = bigquery.Client(project=DASHBOARD_CONFIGURATION["bigquery"]["billing_project"])
    query_parameters = [
        bigquery.ScalarQueryParameter("reporting_year", "INT64", reporting_year),
        bigquery.ScalarQueryParameter("last_calendar_month", "INT64", last_calendar_month),
        bigquery.ScalarQueryParameter("country_name", "STRING", SCOPE["country"]),
        bigquery.ArrayQueryParameter("direct_source_groups", "STRING", list(SCOPE["direct_source_groups"].values())),
        bigquery.ScalarQueryParameter("external_source_group", "STRING", SCOPE["external_source_group"]),
        bigquery.ScalarQueryParameter("external_employee_flag", "STRING", SCOPE["external_employee_flag"]),
        bigquery.ScalarQueryParameter("excluded_absenteeism_reason", "STRING", BUSINESS_RULES["absenteeism_reason_to_exclude"]),
        bigquery.ScalarQueryParameter("unassigned_pbp_label", "STRING", UNASSIGNED_PBP_LABEL),
        bigquery.ArrayQueryParameter("excluded_operational_categories", "STRING", BUSINESS_RULES["operational_categories_to_exclude"]),
        bigquery.ArrayQueryParameter("excluded_location_names", "STRING", BUSINESS_RULES["temporarily_excluded_locations"]),
    ]
    query_job_configuration = bigquery.QueryJobConfig(
        query_parameters=query_parameters,
        use_legacy_sql=False,
        maximum_bytes_billed=MAXIMUM_BYTES_BILLED_PER_QUERY,
    )
    return {
        query_name: [dict(row.items()) for row in client.query(query_sql, job_config=query_job_configuration).result()]
        for query_name, query_sql in build_official_source_queries().items()
    }


def load_source_results_from_json(source_results_json_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Permite generar el HTML desde una extracción controlada, sin conectarse a BQ."""

    return json.loads(source_results_json_path.read_text(encoding="utf-8"))
