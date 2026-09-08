"""Carga exclusivamente la fuente regional utilizada por el dashboard Team TTE.

Este módulo no comparte SQL ni reglas con ``data_loader.py``. La separación es
intencional: permite comparar la versión regional y la homologada sin mezclar sus
fuentes ni presentar una métrica regional como si ya estuviera homologada.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_loader import DASHBOARD_CONFIGURATION, MAXIMUM_BYTES_BILLED_PER_QUERY

TEAM_TTE_REGIONAL_TABLE = DASHBOARD_CONFIGURATION["bigquery"]["tables"]["team_tte_regional_base"]


def build_team_tte_person_month_query() -> str:
    """Devuelve el SQL regional al grano persona × mes × dimensiones vigentes.

    Las métricas de la tabla son aditivas a nivel día. Agruparlas por persona-mes
    reduce aproximadamente cuatro millones de filas de 2026 a unas 239 mil sin
    perder la capacidad de contar personas distintas después de aplicar filtros.
    """

    return f"""
SELECT
  source.ano AS year,
  source.mes AS month,
  CAST(source.consumer_id AS STRING) AS consumer_id,
  COALESCE(NULLIF(TRIM(source.people_business_partner), ''), 'Sin PBP informado') AS people_business_partner,
  COALESCE(NULLIF(TRIM(source.campana), ''), 'Sin Campaña informada') AS campaign,
  COALESCE(NULLIF(TRIM(source.diretor), ''), 'Sin Director informado') AS director,
  COALESCE(NULLIF(TRIM(source.gerente), ''), 'Sin Gerente informado') AS manager,
  COALESCE(NULLIF(TRIM(source.n3), ''), 'Sin N3 informado') AS n3,
  COALESCE(NULLIF(TRIM(source.tier4), ''), 'Sin Tier 4 informado') AS tier4,
  COALESCE(NULLIF(TRIM(source.tier5), ''), 'Sin Tier 5 informado') AS tier5,
  COALESCE(NULLIF(TRIM(source.tier6), ''), 'Sin Tier 6 informado') AS tier6,
  COALESCE(NULLIF(TRIM(source.regiao), ''), 'Sin Región informada') AS region,
  COALESCE(NULLIF(TRIM(source.localidade), ''), 'Sin Localidade informada') AS location,
  COALESCE(NULLIF(TRIM(source.area), ''), 'Sin Área informada') AS area,
  COALESCE(NULLIF(TRIM(source.subarea), ''), 'Sin Subárea informada') AS subarea,
  COALESCE(NULLIF(TRIM(source.cargo), ''), 'Sin Cargo informado') AS role,
  COALESCE(NULLIF(TRIM(source.seniority), ''), 'Sin Seniority informado') AS seniority,
  COALESCE(NULLIF(TRIM(source.status_historico), ''), 'Sin Status informado') AS historical_status,
  COALESCE(NULLIF(TRIM(source.pcd), ''), 'Sin PCD informado') AS pcd,
  COALESCE(NULLIF(TRIM(source.afastado_inss), ''), 'Sin INSS informado') AS inss,
  SUM(COALESCE(source.dotacao_programada, 0)) AS scheduled_population,
  SUM(COALESCE(source.faltas_gestionaveis, 0)) AS manageable_absence,
  SUM(COALESCE(source.faltas_nao_gestionaveis, 0)) AS non_manageable_absence,
  SUM(COALESCE(source.faltas_outros, 0)) AS other_absence,
  SUM(COALESCE(source.hc, 0)) AS monthly_headcount_indicator,
  MAX(CASE
    WHEN DATE_TRUNC(source.data_completa, MONTH) = DATE_TRUNC(CURRENT_DATE(), MONTH)
         AND source.data_completa >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
      THEN 1
    WHEN DATE_TRUNC(source.data_completa, MONTH) != DATE_TRUNC(CURRENT_DATE(), MONTH)
         AND (
           (EXTRACT(MONTH FROM source.data_completa) IN (1,3,5,7,8,10,12) AND EXTRACT(DAY FROM source.data_completa) >= 28) OR
           (EXTRACT(MONTH FROM source.data_completa) IN (4,6,9,11) AND EXTRACT(DAY FROM source.data_completa) >= 27) OR
           (EXTRACT(MONTH FROM source.data_completa) = 2 AND EXTRACT(DAY FROM source.data_completa) >= 25)
         )
      THEN 1
    ELSE 0
  END) AS is_in_average_headcount_snapshot,
  COUNTIF(source.tipo_turnover IS NOT NULL) AS total_turnover,
  COUNTIF(source.tipo_turnover = 'Renuncia') AS resignations,
  COUNTIF(source.tipo_turnover = 'Despido') AS dismissals,
  COUNTIF(source.tipo_turnover = 'No cuenta') AS not_counted_turnover,
  SUM(COALESCE(source.turnover_meta, 0)) AS turnover_target,
  COUNTIF(source.motivo_saida = 'Abandono de emprego') AS job_abandonments,
  COUNTIF(source.motivo_ausentismo = 'enfermedad') AS reason_illness,
  COUNTIF(source.motivo_ausentismo = 'ausencia injustificada') AS reason_unjustified_absence,
  COUNTIF(source.motivo_ausentismo = 'permisos líder') AS reason_leader_permission,
  COUNTIF(source.motivo_ausentismo = 'permiso servicio médico') AS reason_medical_service_permission,
  COUNTIF(source.motivo_ausentismo = 'suspension/sanción') AS reason_suspension_sanction,
  FORMAT_DATE('%Y-%m-%d', MIN(MIN(source.data_completa)) OVER ()) AS source_minimum_date,
  FORMAT_DATE('%Y-%m-%d', MAX(MAX(source.data_completa)) OVER ()) AS source_maximum_date
FROM `{TEAM_TTE_REGIONAL_TABLE}` AS source
WHERE source.ano BETWEEN @first_reporting_year AND @reporting_year
  AND (source.ano < @reporting_year OR source.mes BETWEEN 1 AND @last_calendar_month)
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
"""


def load_team_tte_results_from_bigquery(first_reporting_year: int, reporting_year: int, last_calendar_month: int) -> list[dict[str, Any]]:
    """Ejecuta la consulta regional con parámetros tipados y límite preventivo."""

    try:
        from google.cloud import bigquery
    except ImportError as import_error:
        raise RuntimeError("Falta google-cloud-bigquery. Ejecuta pip install -r requirements.txt") from import_error

    client = bigquery.Client(project=DASHBOARD_CONFIGURATION["bigquery"]["billing_project"])
    query_job_configuration = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("first_reporting_year", "INT64", first_reporting_year),
            bigquery.ScalarQueryParameter("reporting_year", "INT64", reporting_year),
            bigquery.ScalarQueryParameter("last_calendar_month", "INT64", last_calendar_month),
        ],
        use_legacy_sql=False,
        maximum_bytes_billed=MAXIMUM_BYTES_BILLED_PER_QUERY,
    )
    return [
        dict(source_row.items())
        for source_row in client.query(
            build_team_tte_person_month_query(), job_config=query_job_configuration
        ).result()
    ]


def load_team_tte_results_from_json(source_results_json_path: Path) -> list[dict[str, Any]]:
    """Carga una extracción regional controlada para pruebas sin conexión a BQ."""

    return json.loads(source_results_json_path.read_text(encoding="utf-8"))