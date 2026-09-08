"""Punto de entrada: carga → procesa → genera HTML."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from builders import write_dashboard_html
from data_loader import DASHBOARD_CONFIGURATION, load_source_results_from_bigquery, load_source_results_from_json
from processors import compile_monthly_dashboard_cube, compile_monthly_reason_series

PROJECT_ROOT_DIRECTORY = Path(__file__).resolve().parent.parent


def parse_command_line_arguments() -> argparse.Namespace:
    """Define argumentos reproducibles y una alternativa local para datos exportados."""
    current_date = date.today()
    parser = argparse.ArgumentParser(description="Genera el dashboard oficial TTE Brasil.")
    parser.add_argument("--year", type=int, default=current_date.year)
    parser.add_argument("--last-month", type=int, default=current_date.month)
    parser.add_argument("--source-results-json", type=Path)
    parser.add_argument("--output-html", type=Path, default=PROJECT_ROOT_DIRECTORY / DASHBOARD_CONFIGURATION["dashboard"]["output_html_file"])
    return parser.parse_args()


def main() -> None:
    """Ejecuta un flujo lineal, sin lógica de negocio fuera de processors.py."""
    arguments = parse_command_line_arguments()
    if not 1 <= arguments.last_month <= 12:
        raise ValueError("--last-month debe estar entre 1 y 12.")
    source_results = load_source_results_from_json(arguments.source_results_json) if arguments.source_results_json else load_source_results_from_bigquery(arguments.year, arguments.last_month)
    monthly_cube_cells = compile_monthly_dashboard_cube(source_results)
    reason_cells = compile_monthly_reason_series(source_results)
    write_dashboard_html(monthly_cube_cells, reason_cells, arguments.output_html, arguments.year, arguments.last_month)
    print(f"Dashboard generado: {arguments.output_html}")


if __name__ == "__main__":
    main()
