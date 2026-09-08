"""Enriquece métricas homologadas con dimensiones regionales TTE.

Las métricas continúan proviniendo exclusivamente de NOMINA_ALL (tabla física
KPI_LATAM_NC_TO_ALL) y
KPI_LATAM_HYPER_ABS. La tabla regional sólo aporta dimensiones mediante LEFT
JOIN temporal. Un registro sin correspondencia se conserva y se identifica
explícitamente como ``Sin cobertura TTE``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_loader import (
    BUSINESS_RULES,
    DASHBOARD_CONFIGURATION,
    MAXIMUM_BYTES_BILLED_PER_QUERY,
    SCOPE,
    TABLES,
    UNASSIGNED_PBP_LABEL,
    UNASSIGNED_PCD_LABEL,
    UNASSIGNED_SUPERVISOR_LABEL,
)

TEAM_TTE_REGIONAL_TABLE = TABLES["team_tte_regional_base"]
TTE_UNMATCHED_LABEL = "Sin cobertura TTE"

REGIONAL_DIMENSION_SOURCE_COLUMNS = {
    "tte_campaign": ("campana", "Sin Campaña informada"),
    "tte_director": ("diretor", "Sin Director informado"),
    "tte_manager": ("gerente", "Sin Gerente informado"),
    "tte_n3": ("n3", "Sin N3 informado"),
    "tte_region": ("regiao", "Sin Región TTE informada"),
    "tte_tier4": ("tier4", "Sin Tier 4 informado"),
    "tte_tier5": ("tier5", "Sin Tier 5 informado"),
    "tte_tier6": ("tier6", "Sin Tier 6 informado"),
    "tte_location": ("localidade", "Sin Localidade informada"),
    "tte_role": ("cargo", "Sin Cargo informado"),
    "tte_seniority": ("seniority", "Sin Seniority informado"),
    "tte_historical_status": ("status_historico", "Sin Status informado"),
    "tte_inss": ("afastado_inss", "Sin INSS informado"),
}


def build_tte_dimension_projection(source_alias: str) -> str:
    """Proyecta los campos regionales crudos necesarios para los puentes temporales."""

    projected_columns = [
        f"{source_alias}.{source_column_name} AS {output_column_name}"
        for output_column_name, (source_column_name, _) in REGIONAL_DIMENSION_SOURCE_COLUMNS.items()
    ]
    return ",\n    ".join(projected_columns)


def build_tte_enriched_dimension_expressions(tte_alias: str) -> str:
    """Diferencia ausencia de match de un campo vacío dentro de un match válido."""

    expressions = [
        f"CASE WHEN {tte_alias}.consumer_id IS NULL THEN '{TTE_UNMATCHED_LABEL}' ELSE 'Con cobertura TTE' END AS tte_coverage_status"
    ]
    for output_column_name, (_, missing_value_label) in REGIONAL_DIMENSION_SOURCE_COLUMNS.items():
        expressions.append(
            f"CASE WHEN {tte_alias}.consumer_id IS NULL THEN '{TTE_UNMATCHED_LABEL}' "
            f"ELSE COALESCE(NULLIF(TRIM({tte_alias}.{output_column_name}), ''), '{missing_value_label}') "
            f"END AS {output_column_name}"
        )
    return ",\n  ".join(expressions)


def build_unmatched_tte_dimension_expressions() -> str:
    """Genera dimensiones regionales explícitamente no cubiertas para Externos."""

    expressions = [f"'{TTE_UNMATCHED_LABEL}' AS tte_coverage_status"]
    expressions.extend(
        f"'{TTE_UNMATCHED_LABEL}' AS {output_column_name}"
        for output_column_name in REGIONAL_DIMENSION_SOURCE_COLUMNS
    )
    return ",\n  ".join(expressions)


REGIONAL_GROUP_BY_COLUMNS = ["tte_coverage_status", *REGIONAL_DIMENSION_SOURCE_COLUMNS]
COMMON_OUTPUT_GROUP_BY_COLUMNS = [
    "year", "month", "source_group", "site_operativo", "area", "subarea",
    "pbp", "pcd", "supervisor", "region", "operation_type",
    *REGIONAL_GROUP_BY_COLUMNS,
]


def comma_separated_group_by(column_names: list[str]) -> str:
    """Mantiene el GROUP BY legible y alineado con el contrato publicado."""

    return ", ".join(column_names)


def build_enriched_direct_population_condition(tte_alias: str) -> str:
    """Amplía la tercera vista sólo cuando existe un match TTE válido.

    Los grupos homologados originales permanecen incluso sin match regional. Los
    demás Seniorities se incorporan sólo cuando ``Agrupador_1`` coincide exactamente
    con el Seniority TTE de la misma persona y periodo.
    """

    return f"""(
    source.Agrupador_1 IN UNNEST(@direct_source_groups)
    OR (
      {tte_alias}.consumer_id IS NOT NULL
      AND source.Agrupador_1 = {tte_alias}.tte_seniority
    )
  )"""

def build_tte_daily_dimensions_cte() -> str:
    """Crea un puente 1:1 persona-fecha; la unicidad fue validada en la fuente."""

    return f"""tte_daily_dimensions AS (
  SELECT
    source.data_completa,
    source.consumer_id,
    {build_tte_dimension_projection('source')}
  FROM `{TEAM_TTE_REGIONAL_TABLE}` AS source
  WHERE source.ano = @reporting_year
    AND source.mes BETWEEN 1 AND @last_calendar_month
)"""


def build_tte_month_end_dimensions_cte() -> str:
    """Elige deterministicamente la última dimensión disponible por persona-mes."""

    return f"""tte_month_end_dimensions AS (
  SELECT
    source.ano,
    source.mes,
    source.consumer_id,
    {build_tte_dimension_projection('source')}
  FROM `{TEAM_TTE_REGIONAL_TABLE}` AS source
  WHERE source.ano = @reporting_year
    AND source.mes BETWEEN 1 AND @last_calendar_month
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY source.ano, source.mes, source.consumer_id
    ORDER BY source.data_completa DESC
  ) = 1
)"""


def build_homologated_tte_enriched_queries() -> dict[str, str]:
    """Construye consultas que preservan las métricas oficiales antes de agregar."""

    location_join_for_workforce = f"""LEFT JOIN `{TABLES['location_catalog']}` AS location_catalog
  ON source.Pais_Region = location_catalog.Pais_Region
 AND UPPER(TRIM(source.Ubicacion__Nombre)) = UPPER(TRIM(location_catalog.Ubicacion__Nombre))"""
    location_join_for_absenteeism = f"""LEFT JOIN `{TABLES['location_catalog']}` AS location_catalog
  ON source.Pais_region = location_catalog.Pais_Region
 AND UPPER(TRIM(source.ubicacion)) = UPPER(TRIM(location_catalog.Ubicacion__Nombre))"""
    supervisor_directory_join_for_workforce = f"""LEFT JOIN (
  SELECT Ano, Mes, CAST(ID_de_usuario_empleado AS STRING) AS employee_id,
         ANY_VALUE(NULLIF(UPPER(TRIM(Nombre_de_usuario)), '')) AS supervisor_username
  FROM `{TABLES['nomina_all']}`
  WHERE Ano = @reporting_year AND Mes BETWEEN 1 AND @last_calendar_month
    AND Pais_Region = @country_name
  GROUP BY 1,2,3
) AS supervisor_directory
  ON source.Ano = supervisor_directory.Ano
 AND source.Mes = supervisor_directory.Mes
 AND CAST(source.ID_de_sistema_del_usuario_lider AS STRING) = supervisor_directory.employee_id"""
    common_workforce_dimensions = """source.Ano AS year, source.Mes AS month, source.Agrupador_1 AS source_group,
  UPPER(TRIM(source.Ubicacion__Nombre)) AS site_operativo,
  source.Area AS area, source.Subarea AS subarea,
  COALESCE(NULLIF(UPPER(TRIM(source.People_Business_Partner__People_BP_Supervisores_Adicionales_Nombre)), ''), @unassigned_pbp_label) AS pbp,
  COALESCE(NULLIF(TRIM(source.Posee_Discapacidad), ''), @unassigned_pcd_label) AS pcd,
  COALESCE(supervisor_directory.supervisor_username, @unassigned_supervisor_label) AS supervisor,
  location_catalog.Region AS region, location_catalog.Site AS operation_type"""

    headcount_select = f"""SELECT
  {common_workforce_dimensions},
  {build_tte_enriched_dimension_expressions('tte_dimensions')},
  source.Tipo AS record_type,
  CAST(NULL AS STRING) AS attrition_type,
  CAST(NULL AS STRING) AS attrition_reason,
  COUNT(DISTINCT source.ID_de_usuario_empleado) AS value
FROM `{TABLES['nomina_all']}` AS source
{location_join_for_workforce}
{supervisor_directory_join_for_workforce}
LEFT JOIN tte_month_end_dimensions AS tte_dimensions
  ON source.Ano = tte_dimensions.ano
 AND source.Mes = tte_dimensions.mes
 AND CAST(source.ID_de_usuario_empleado AS STRING) = tte_dimensions.consumer_id
WHERE source.Ano = @reporting_year AND source.Mes BETWEEN 1 AND @last_calendar_month
  AND source.Pais_Region = @country_name
  AND {build_enriched_direct_population_condition('tte_dimensions')}
  AND source.Tipo IN ('Headcount Historico', 'Headcount Actual')
  AND (location_catalog.Site IS NULL OR location_catalog.Site NOT IN UNNEST(@excluded_operational_categories))
  AND UPPER(TRIM(source.Ubicacion__Nombre)) NOT IN UNNEST(@excluded_location_names)
GROUP BY {comma_separated_group_by(COMMON_OUTPUT_GROUP_BY_COLUMNS + ['record_type', 'attrition_type', 'attrition_reason'])}"""

    attrition_select = f"""SELECT
  {common_workforce_dimensions},
  {build_tte_enriched_dimension_expressions('tte_dimensions')},
  source.Tipo AS record_type,
  source.tipoBaja AS attrition_type,
  source.motivosDeSalida AS attrition_reason,
  COUNT(DISTINCT source.ID_de_usuario_empleado) AS value
FROM `{TABLES['nomina_all']}` AS source
{location_join_for_workforce}
{supervisor_directory_join_for_workforce}
LEFT JOIN tte_daily_dimensions AS tte_dimensions
  ON source.Datos_Laborales_Fecha_de_terminacion = tte_dimensions.data_completa
 AND CAST(source.ID_de_usuario_empleado AS STRING) = tte_dimensions.consumer_id
WHERE source.Ano = @reporting_year AND source.Mes BETWEEN 1 AND @last_calendar_month
  AND source.Pais_Region = @country_name
  AND {build_enriched_direct_population_condition('tte_dimensions')}
  AND source.Tipo = 'Bajas'
  AND (location_catalog.Site IS NULL OR location_catalog.Site NOT IN UNNEST(@excluded_operational_categories))
  AND UPPER(TRIM(source.Ubicacion__Nombre)) NOT IN UNNEST(@excluded_location_names)
GROUP BY {comma_separated_group_by(COMMON_OUTPUT_GROUP_BY_COLUMNS + ['record_type', 'attrition_type', 'attrition_reason'])}"""

    direct_headcount_and_attrition = f"""WITH
{build_tte_daily_dimensions_cte()},
{build_tte_month_end_dimensions_cte()}
{headcount_select}
UNION ALL
{attrition_select}"""

    direct_hirings = f"""WITH
{build_tte_daily_dimensions_cte()}
SELECT
  EXTRACT(YEAR FROM source.Datos_Laborales_Fecha_de_contratacion) AS year,
  EXTRACT(MONTH FROM source.Datos_Laborales_Fecha_de_contratacion) AS month,
  source.Agrupador_1 AS source_group,
  UPPER(TRIM(source.Ubicacion__Nombre)) AS site_operativo,
  source.Area AS area, source.Subarea AS subarea,
  COALESCE(NULLIF(UPPER(TRIM(source.People_Business_Partner__People_BP_Supervisores_Adicionales_Nombre)), ''), @unassigned_pbp_label) AS pbp,
  COALESCE(NULLIF(TRIM(source.Posee_Discapacidad), ''), @unassigned_pcd_label) AS pcd,
  COALESCE(supervisor_directory.supervisor_username, @unassigned_supervisor_label) AS supervisor,
  location_catalog.Region AS region, location_catalog.Site AS operation_type,
  {build_tte_enriched_dimension_expressions('tte_dimensions')},
  COUNT(DISTINCT source.ID_de_usuario_empleado) AS value
FROM `{TABLES['nomina_all']}` AS source
{location_join_for_workforce}
{supervisor_directory_join_for_workforce}
LEFT JOIN tte_daily_dimensions AS tte_dimensions
  ON source.Datos_Laborales_Fecha_de_contratacion = tte_dimensions.data_completa
 AND CAST(source.ID_de_usuario_empleado AS STRING) = tte_dimensions.consumer_id
WHERE source.Pais_Region = @country_name
  AND {build_enriched_direct_population_condition('tte_dimensions')}
  AND EXTRACT(YEAR FROM source.Datos_Laborales_Fecha_de_contratacion) = @reporting_year
  AND EXTRACT(MONTH FROM source.Datos_Laborales_Fecha_de_contratacion) BETWEEN 1 AND @last_calendar_month
  AND (location_catalog.Site IS NULL OR location_catalog.Site NOT IN UNNEST(@excluded_operational_categories))
  AND UPPER(TRIM(source.Ubicacion__Nombre)) NOT IN UNNEST(@excluded_location_names)
GROUP BY {comma_separated_group_by(COMMON_OUTPUT_GROUP_BY_COLUMNS)}"""

    external_headcount_and_attrition = f"""SELECT
  source.Ano AS year, source.Mes AS month, source.Agrupador_1 AS source_group,
  UPPER(TRIM(source.Ubicacion__Nombre)) AS site_operativo,
  source.Area AS area, source.Subarea AS subarea,
  COALESCE(NULLIF(UPPER(TRIM(source.People_Business_Partner__People_BP_Supervisores_Adicionales_Nombre)), ''), @unassigned_pbp_label) AS pbp,
  COALESCE(NULLIF(TRIM(source.Posee_Discapacidad), ''), @unassigned_pcd_label) AS pcd,
  @unassigned_supervisor_label AS supervisor,
  location_catalog.Region AS region, location_catalog.Site AS operation_type,
  {build_unmatched_tte_dimension_expressions()},
  source.Tipo AS record_type,
  source.tipoBaja AS attrition_type,
  source.motivosDeSalida AS attrition_reason,
  COUNT(*) AS value
FROM `{TABLES['nomina_all']}` AS source
{location_join_for_workforce}
WHERE source.Ano = @reporting_year AND source.Mes BETWEEN 1 AND @last_calendar_month
  AND source.Pais_Region = @country_name
  AND source.Agrupador_1 = @external_source_group
  AND source.Tipo IN ('Headcount Historico', 'Headcount Actual', 'Bajas')
  AND (location_catalog.Site IS NULL OR location_catalog.Site NOT IN UNNEST(@excluded_operational_categories))
  AND UPPER(TRIM(source.Ubicacion__Nombre)) NOT IN UNNEST(@excluded_location_names)
GROUP BY {comma_separated_group_by(COMMON_OUTPUT_GROUP_BY_COLUMNS + ['record_type', 'attrition_type', 'attrition_reason'])}"""

    absenteeism = f"""WITH
{build_tte_daily_dimensions_cte()}
SELECT
  source.Ano AS year, source.Mes AS month, source.Agrupador_1 AS source_group,
  source.colaborador_externo AS external_employee,
  UPPER(TRIM(source.ubicacion)) AS site_operativo,
  source.Area AS area, source.Subarea AS subarea,
  COALESCE(NULLIF(UPPER(TRIM(source.Pbp)), ''), @unassigned_pbp_label) AS pbp,
  COALESCE(NULLIF(TRIM(source.Posee_Discapacidad), ''), @unassigned_pcd_label) AS pcd,
  CASE WHEN source.colaborador_externo = @external_employee_flag THEN @unassigned_supervisor_label
       ELSE COALESCE(NULLIF(UPPER(TRIM(source.Supervisor)), ''), @unassigned_supervisor_label) END AS supervisor,
  location_catalog.Region AS region,
  CASE WHEN source.CAT_TA = 'No MAP' AND UPPER(TRIM(source.ubicacion)) IN ('BRES01', 'BRPR01') THEN 'Full'
       ELSE source.CAT_TA END AS operation_type,
  {build_tte_enriched_dimension_expressions('tte_dimensions')},
  source.Motivo_ausentismo AS absenteeism_reason,
  SUM(source.Dotacion_programada) AS scheduled_workforce,
  SUM(source.Ausentismo_gestionable) AS manageable_absenteeism,
  SUM(source.Ausentismo_No_Gestionable) AS non_manageable_absenteeism,
  SUM(source.Ausentismo_otros) AS other_absenteeism
FROM `{TABLES['official_absenteeism']}` AS source
{location_join_for_absenteeism}
LEFT JOIN tte_daily_dimensions AS tte_dimensions
  ON source.Dia = tte_dimensions.data_completa
 AND CAST(source.NK_Dim_Empleado AS STRING) = tte_dimensions.consumer_id
WHERE source.Ano = @reporting_year AND source.Mes BETWEEN 1 AND @last_calendar_month
  AND source.Pais_region = @country_name
  AND source.Motivo_ausentismo != @excluded_absenteeism_reason
  AND source.CAT_TA NOT IN UNNEST(@excluded_operational_categories)
  AND UPPER(TRIM(source.ubicacion)) NOT IN UNNEST(@excluded_location_names)
  AND (
    source.colaborador_externo = @external_employee_flag
    OR {build_enriched_direct_population_condition('tte_dimensions')}
  )
GROUP BY {comma_separated_group_by(COMMON_OUTPUT_GROUP_BY_COLUMNS + ['external_employee', 'absenteeism_reason'])}"""

    return {
        "direct_headcount_and_attrition": direct_headcount_and_attrition,
        "direct_hirings": direct_hirings,
        "external_headcount_and_attrition": external_headcount_and_attrition,
        "absenteeism": absenteeism,
    }


def load_homologated_tte_enriched_results_from_bigquery(reporting_year: int, last_calendar_month: int) -> dict[str, list[dict[str, Any]]]:
    """Ejecuta el prototipo enriquecido sin modificar las consultas homologadas."""

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
        bigquery.ScalarQueryParameter("unassigned_pcd_label", "STRING", UNASSIGNED_PCD_LABEL),
        bigquery.ScalarQueryParameter("unassigned_supervisor_label", "STRING", UNASSIGNED_SUPERVISOR_LABEL),
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
        for query_name, query_sql in build_homologated_tte_enriched_queries().items()
    }


def load_homologated_tte_enriched_results_from_json(source_results_json_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Carga una extracción enriquecida reproducible sin conexión a BigQuery."""

    return json.loads(source_results_json_path.read_text(encoding="utf-8"))