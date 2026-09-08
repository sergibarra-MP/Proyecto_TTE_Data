"""Pruebas unitarias del contrato regional; no consultan BigQuery."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SOURCE_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_DIRECTORY))

from team_tte_data_loader import build_team_tte_person_month_query
from team_tte_processors import compile_team_tte_dashboard_payload


class TeamTteRegionalContractTests(unittest.TestCase):
    def test_query_uses_only_regional_table_and_multiyear_parameters(self) -> None:
        query = build_team_tte_person_month_query()
        self.assertIn("TTE_BRASIL_TABELA_BASE_PEOPLEBUSINESSPARTNER", query)
        self.assertIn("@first_reporting_year", query)
        self.assertIn("@reporting_year", query)
        self.assertIn("source.afastado_inss", query)
        self.assertIn("is_in_average_headcount_snapshot", query)
        self.assertNotIn("KPI_LATAM_NC_TO_ALL", query)
        self.assertNotIn("KPI_LATAM_HYPER_ABS", query)

    def test_processor_preserves_person_identifier_and_snapshot_indicator(self) -> None:
        source_row = {
            "year": 2026, "month": 9, "consumer_id": "person-1",
            "people_business_partner": "PBP", "campaign": "Campaña", "director": "Director",
            "manager": "Gerente", "n3": "N3", "tier4": "T4", "tier5": "T5", "tier6": "T6",
            "region": "Región", "location": "Localidade", "area": "Área", "subarea": "Subárea",
            "role": "Cargo", "seniority": "Non CDBR", "historical_status": "ativo",
            "pcd": "nao", "inss": "nao", "source_minimum_date": "2024-01-01",
            "source_maximum_date": "2026-09-07", "is_in_average_headcount_snapshot": 1,
            "scheduled_population": 7, "manageable_absence": 1,
        }
        payload = compile_team_tte_dashboard_payload([source_row])
        self.assertEqual(payload["sourceMinimumDate"], "2024-01-01")
        self.assertEqual(payload["sourceMaximumDate"], "2026-09-07")
        self.assertEqual(payload["cells"][0]["consumerId"], "person-1")
        self.assertEqual(payload["cells"][0]["is_in_average_headcount_snapshot"], 1.0)
        self.assertEqual(payload["cells"][0]["scheduled_population"], 7.0)


if __name__ == "__main__":
    unittest.main()