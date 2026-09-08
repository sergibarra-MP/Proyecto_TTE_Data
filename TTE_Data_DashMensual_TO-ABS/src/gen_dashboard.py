"""Punto de entrada: carga independiente → procesa → genera HTML con dos vistas."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from builders import write_dashboard_html
from data_loader import (
    DASHBOARD_CONFIGURATION,
    load_source_results_from_bigquery,
    load_source_results_from_json,
)
from processors import compile_monthly_dashboard_cube, compile_monthly_reason_series
from team_tte_data_loader import (
    load_team_tte_results_from_bigquery,
    load_team_tte_results_from_json,
)
from team_tte_processors import compile_team_tte_dashboard_payload

PROJECT_ROOT_DIRECTORY = Path(__file__).resolve().parent.parent


def parse_command_line_arguments() -> argparse.Namespace:
    """Define argumentos reproducibles y alternativas locales para ambas fuentes."""

    current_date = date.today()
    parser = argparse.ArgumentParser(description="Genera las vistas Homologada y Team TTE Brasil.")
    parser.add_argument("--first-year", type=int, default=DASHBOARD_CONFIGURATION["team_tte"].get("first_available_year", 2024))
    parser.add_argument("--year", type=int, default=current_date.year)
    parser.add_argument("--last-month", type=int, default=current_date.month)
    parser.add_argument("--source-results-json", type=Path)
    parser.add_argument("--team-tte-source-results-json", type=Path)
    parser.add_argument(
        "--output-html",
        type=Path,
        default=PROJECT_ROOT_DIRECTORY / DASHBOARD_CONFIGURATION["dashboard"]["output_html_file"],
    )
    return parser.parse_args()


def main() -> None:
    """Ejecuta cada fuente por separado y sólo las une en el contenedor HTML."""

    arguments = parse_command_line_arguments()
    if arguments.first_year > arguments.year:
        raise ValueError("--first-year no puede ser mayor que --year.")
    if not 1 <= arguments.last_month <= 12:
        raise ValueError("--last-month debe estar entre 1 y 12.")

    if arguments.source_results_json:
        homologated_source_results = load_source_results_from_json(arguments.source_results_json)
    else:
        homologated_source_results = load_source_results_from_bigquery(arguments.year, arguments.last_month)

    if arguments.team_tte_source_results_json:
        regional_source_rows = load_team_tte_results_from_json(arguments.team_tte_source_results_json)
    elif arguments.source_results_json:
        # Una prueba local de la vista homologada no debe conectarse silenciosamente a BigQuery.
        regional_source_rows = []
    else:
        regional_source_rows = load_team_tte_results_from_bigquery(arguments.first_year, arguments.year, arguments.last_month)

    monthly_cube_cells = compile_monthly_dashboard_cube(homologated_source_results)
    reason_cells = compile_monthly_reason_series(homologated_source_results)
    team_tte_payload = compile_team_tte_dashboard_payload(regional_source_rows)
    write_dashboard_html(
        monthly_cube_cells,
        reason_cells,
        team_tte_payload,
        arguments.output_html,
        arguments.year,
        arguments.last_month,
    )
    print(f"Dashboard generado: {arguments.output_html}")
    print(f"Vista Homologada: {len(monthly_cube_cells):,} celdas mensuales y {len(reason_cells):,} celdas de motivos.")
    print(f"Vista Team TTE: {len(team_tte_payload['cells']):,} celdas persona-mes regionales.")


if __name__ == "__main__":
    main()