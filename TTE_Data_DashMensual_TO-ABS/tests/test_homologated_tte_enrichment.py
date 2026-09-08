"""Pruebas de regresión para el cruce Homologado+TTE."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SOURCE_DIRECTORY = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_DIRECTORY))

from homologated_tte_enrichment_loader import (  # noqa: E402
    TTE_UNMATCHED_LABEL,
    build_homologated_tte_enriched_queries,
)
from homologated_tte_enrichment_processors import (  # noqa: E402
    compile_homologated_tte_enriched_cube,
)


class HomologatedTteQueryTests(unittest.TestCase):
    def test_melicidade_is_excluded_from_every_official_metric_family(self) -> None:
        queries = build_homologated_tte_enriched_queries()
        workforce_condition = "location_catalog.Site NOT IN UNNEST(@excluded_operational_categories)"

        self.assertIn(workforce_condition, queries["direct_headcount_and_attrition"])
        self.assertIn(workforce_condition, queries["direct_hirings"])
        self.assertIn(workforce_condition, queries["external_headcount_and_attrition"])
        self.assertIn("source.CAT_TA NOT IN UNNEST(@excluded_operational_categories)", queries["absenteeism"])
    def test_regional_dimensions_are_attached_with_left_joins(self) -> None:
        queries = build_homologated_tte_enriched_queries()

        self.assertIn("LEFT JOIN tte_month_end_dimensions", queries["direct_headcount_and_attrition"])
        self.assertIn("LEFT JOIN tte_daily_dimensions", queries["direct_headcount_and_attrition"])
        self.assertIn("source.Datos_Laborales_Fecha_de_contratacion = tte_dimensions.data_completa", queries["direct_hirings"])
        self.assertIn("source.Dia = tte_dimensions.data_completa", queries["absenteeism"])
        self.assertIn("ROW_NUMBER() OVER", queries["direct_headcount_and_attrition"])

    def test_external_population_is_kept_as_explicitly_unmatched(self) -> None:
        external_query = build_homologated_tte_enriched_queries()["external_headcount_and_attrition"]

        self.assertIn(f"'{TTE_UNMATCHED_LABEL}' AS tte_coverage_status", external_query)
        self.assertNotIn("JOIN tte_daily_dimensions", external_query)


class HomologatedTteProcessorTests(unittest.TestCase):
    @staticmethod
    def direct_row(**overrides: object) -> dict[str, object]:
        row: dict[str, object] = {
            "year": 2026,
            "month": 1,
            "source_group": "Representante",
            "site_operativo": "SITE",
            "area": "AREA",
            "subarea": "SUBAREA",
            "pbp": "PBP",
            "pcd": "No",
            "supervisor": "SUPERVISOR",
            "region": "REGIÓN OFICIAL",
            "operation_type": "FULL",
            "tte_coverage_status": "Con cobertura TTE",
            "tte_campaign": "CAMPAÑA",
            "tte_director": "DIRECTOR",
            "tte_manager": "GERENTE",
            "tte_n3": "N3",
            "tte_region": "REGIÓN TTE",
            "tte_tier4": "T4",
            "tte_tier5": "T5",
            "tte_tier6": "T6",
            "tte_location": "LOCALIDADE",
            "tte_role": "CARGO",
            "tte_seniority": "SENIORITY",
            "tte_historical_status": "ATIVO",
            "tte_inss": "NAO",
            "record_type": "Headcount Historico",
            "attrition_type": None,
            "attrition_reason": None,
            "value": 10,
        }
        row.update(overrides)
        return row

    def test_official_region_and_regional_region_coexist(self) -> None:
        cells = compile_homologated_tte_enriched_cube({
            "direct_headcount_and_attrition": [self.direct_row()],
        })

        self.assertEqual(cells[0]["region"], "REGIÓN OFICIAL")
        self.assertEqual(cells[0]["tteRegion"], "REGIÓN TTE")
        self.assertEqual(cells[0]["headcount"], 10.0)

    def test_unmatched_dimensions_do_not_remove_official_metric(self) -> None:
        unmatched_row = self.direct_row(
            tte_coverage_status=TTE_UNMATCHED_LABEL,
            tte_campaign=TTE_UNMATCHED_LABEL,
            value=7,
        )
        cells = compile_homologated_tte_enriched_cube({
            "direct_headcount_and_attrition": [unmatched_row],
        })

        self.assertEqual(cells[0]["tteCoverageStatus"], TTE_UNMATCHED_LABEL)
        self.assertEqual(cells[0]["tteCampaign"], TTE_UNMATCHED_LABEL)
        self.assertEqual(cells[0]["headcount"], 7.0)

class HomologatedTteExpandedSeniorityTests(unittest.TestCase):
    def test_additional_seniority_requires_exact_regional_match(self) -> None:
        queries = build_homologated_tte_enriched_queries()
        self.assertIn("source.Agrupador_1 = tte_dimensions.tte_seniority", queries["direct_headcount_and_attrition"])

        additional_seniority_row = HomologatedTteProcessorTests.direct_row(
            source_group="Team Leader",
            tte_seniority="Team Leader",
            value=5,
        )
        cells = compile_homologated_tte_enriched_cube({
            "direct_headcount_and_attrition": [additional_seniority_row],
        })
        self.assertEqual(cells[0]["segment"], "Otros Seniorities TTE")
        self.assertEqual(cells[0]["headcount"], 5.0)

class HomologatedTteTemplateTests(unittest.TestCase):
    def test_heavy_views_are_lazy_and_filter_catalogues_are_dependent_and_cached(self) -> None:
        template = (SOURCE_DIRECTORY / "template_dashboard.html").read_text(encoding="utf-8")

        self.assertIn("window.initializeHomologatedTteDashboard", template)
        self.assertIn("window.initializeTeamTteDashboard", template)
        self.assertIn("cachedOptionsByFilterId", template)
        self.assertIn("cachedRegionalOptionsByFilterId", template)
        self.assertIn("dependencySignatureFor", template)
        self.assertIn("regionalDependencySignatureFor", template)
        self.assertIn("candidate.id!==definition.id", template)
        self.assertIn("candidate.id !== definition.id", template)
        self.assertIn('details.addEventListener("toggle"', template)
        self.assertNotIn("data.cells.filter(row=>filterDefinitions.filter", template)

    def test_metric_contract_names_are_not_changed_by_dom_identifiers(self) -> None:
        template = (SOURCE_DIRECTORY / "template_dashboard.html").read_text(encoding="utf-8")

        self.assertIn('"resignations"', template)
        self.assertIn("row.attritionType", template)
        self.assertNotIn("row.homologatedTteAttritionType", template)
        self.assertNotIn("cell.homologatedTteResignations", template)

if __name__ == "__main__":
    unittest.main()