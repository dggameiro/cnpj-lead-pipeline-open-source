"""
Automated unit tests for data pipeline and SQLite database operations.
Validates sanitization routines, configuration loading, CRUD operations,
digital presence qualification, and CSV export functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.cleaner import (
    clean_cnpj,
    format_cnpj,
    validate_cnpj,
    format_phone,
    normalize_company,
)
from src.database import (
    init_db,
    save_cnaes,
    insert_company,
    list_companies,
    update_prospecting_status,
    get_metrics,
    export_leads_to_csv,
)
from src.digital_checker import (
    analyze_layer_1,
    analyze_layer_2,
    analyze_layer_3_http,
    classify_digital_maturity,
    enrich_company_digital,
)
from src.extractor import ingest_radar_cnpj_export
from src.pipeline import run_pipeline
from src.config import load_config, get_city_state, get_default_area_code
from src.dashboard import generate_html_dashboard


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.test_db = Path("database/test_temp.db")
        self.test_csv = Path("data/test_temp.csv")
        self.test_html = Path("data/test_temp.html")
        if self.test_db.exists():
            self.test_db.unlink()
        if self.test_csv.exists():
            self.test_csv.unlink()
        if self.test_html.exists():
            self.test_html.unlink()
        init_db(self.test_db)
        save_cnaes(
            [
                {"code": "4781400", "description": "Vestuário", "segment": "Moda e Vestuário"},
                {"code": "4772500", "description": "Cosméticos", "segment": "Beleza e Cosméticos"},
                {"code": "4782201", "description": "Calçados", "segment": "Calçados e Bolsas"},
            ],
            db_path=self.test_db,
        )

    def tearDown(self):
        if self.test_db.exists():
            self.test_db.unlink()
        if self.test_csv.exists():
            self.test_csv.unlink()
        if self.test_html.exists():
            self.test_html.unlink()

    def test_config_loader(self):
        """Validates configuration loading of regional parameters and target segments."""
        config = load_config()
        self.assertTrue("location" in config)
        city, state = get_city_state()
        self.assertEqual(city, "LONDRINA")
        self.assertEqual(state, "PR")
        self.assertEqual(get_default_area_code(), "43")

    def test_clean_and_format_cnpj(self):
        """Tests CNPJ non-numeric character removal, formatting, and validation."""
        raw_cnpj = " 18.492.049/0001-85 "
        self.assertEqual(clean_cnpj(raw_cnpj), "18492049000185")
        self.assertEqual(format_cnpj("18492049000185"), "18.492.049/0001-85")
        self.assertTrue(validate_cnpj("18492049000185"))
        self.assertFalse(validate_cnpj("11111111111111"))
        self.assertFalse(validate_cnpj("123"))

    def test_format_phone(self):
        """Tests phone number mask application and default area code fallback."""
        self.assertEqual(format_phone("43991234567"), "(43) 99123-4567")
        self.assertEqual(format_phone("4333218899"), "(43) 3321-8899")
        # Numbers without area code receive configured default (43)
        self.assertEqual(format_phone("991234567"), "(43) 99123-4567")

    def test_normalize_company(self):
        """Validates complete company record normalization and enum conversion."""
        raw_record = {
            "cnpj": "18.492.049/0001-85",
            "razao_social": "  londrina fashion boutique ltda  ",
            "nome_fantasia": "  boutique bella flor  ",
            "bairro": "centro",
            "telefone": "43991234567",
            "email": "CONTATO@BELLAFLOR.COM.BR",
            "cnae_fiscal": "4781-4/00",
            "situacao_cadastral": "ATIVA",
            "status_prospeccao": "NOVO",
        }
        normalized = normalize_company(raw_record)
        self.assertEqual(normalized["cnpj"], "18492049000185")
        self.assertEqual(normalized["legal_name"], "LONDRINA FASHION BOUTIQUE LTDA")
        self.assertEqual(normalized["trade_name"], "Boutique Bella Flor")
        self.assertEqual(normalized["neighborhood"], "Centro")
        self.assertEqual(normalized["email"], "contato@bellaflor.com.br")
        self.assertEqual(normalized["phone"], "(43) 99123-4567")
        self.assertEqual(normalized["primary_cnae"], "4781400")
        self.assertEqual(normalized["city"], "LONDRINA")
        self.assertEqual(normalized["state"], "PR")
        self.assertEqual(normalized["registration_status"], "ACTIVE")
        self.assertEqual(normalized["prospecting_status"], "NEW")

    def test_database_crud_metrics_and_csv(self):
        """Tests company insertion, query, status update, metrics aggregation, and CSV export."""
        company = {
            "cnpj": "18492049000185",
            "legal_name": "LONDRINA FASHION",
            "trade_name": "Bella Flor",
            "registration_status": "ACTIVE",
            "opening_date": "2020-01-01",
            "primary_cnae": "4781400",
            "street": "Rua Sergipe",
            "number": "645",
            "neighborhood": "Centro",
            "city": "LONDRINA",
            "state": "PR",
            "zip_code": "86010140",
            "phone": "(43) 99123-4567",
            "email": "contato@bellaflor.com",
            "prospecting_status": "NEW",
        }
        self.assertTrue(insert_company(company, db_path=self.test_db))

        # Query by neighborhood
        companies_list = list_companies(neighborhood="Centro", db_path=self.test_db)
        self.assertEqual(len(companies_list), 1)
        self.assertEqual(companies_list[0]["cnpj"], "18492049000185")
        self.assertEqual(companies_list[0]["legal_name"], "LONDRINA FASHION")

        # Status update
        self.assertTrue(update_prospecting_status("18492049000185", "CONTACTED", db_path=self.test_db))
        updated_list = list_companies(status="CONTACTED", db_path=self.test_db)
        self.assertEqual(len(updated_list), 1)

        # Metrics aggregation
        metrics = get_metrics(db_path=self.test_db)
        self.assertEqual(metrics["total_companies"], 1)
        self.assertEqual(metrics["segments"][0]["segment"], "Moda e Vestuário")

        # CSV export
        exported_count = export_leads_to_csv(output_path=self.test_csv, db_path=self.test_db)
        self.assertEqual(exported_count, 1)
        self.assertTrue(self.test_csv.exists())

    def test_radar_cnpj_integration(self):
        """Validates ingestion from radar-cnpj JSON export file."""
        sample_file = Path("data/export_radar_cnpj_londrina.json")
        if not sample_file.exists():
            sample_file = Path("data/export_radar_sample.json")
        ingested_count = ingest_radar_cnpj_export(sample_file)
        self.assertGreaterEqual(ingested_count, 1)

    def test_pipeline_local_execution(self):
        """Validates local pipeline orchestration run."""
        processed_count = run_pipeline(source="local")
        self.assertGreaterEqual(processed_count, 1)

    def test_enrichment_layers_1_and_2(self):
        """Tests layer 1 (CNAE/email) and layer 2 (domain syntax) checks."""
        # Case 1: Company with e-commerce secondary CNAE and corporate email
        comp1 = {
            "primary_cnae": "4781400",
            "secondary_cnaes": "4791-2/01, 4782201",
            "email": "contato@boutiquemoderna.com.br"
        }
        has_ecom1, domain1 = analyze_layer_1(comp1)
        self.assertEqual(has_ecom1, 1)
        self.assertEqual(domain1, "boutiquemoderna.com.br")
        self.assertEqual(analyze_layer_2(domain1), "https://www.boutiquemoderna.com.br")

        # Case 2: Company without e-commerce CNAE and with free email domain
        comp2 = {
            "primary_cnae": "4781400",
            "email": "loja.londrina@gmail.com"
        }
        has_ecom2, domain2 = analyze_layer_1(comp2)
        self.assertEqual(has_ecom2, 0)
        self.assertIsNone(domain2)
        self.assertIsNone(analyze_layer_2(domain2))

    def test_digital_maturity_classification(self):
        """Tests digital maturity rules across all four categories."""
        # 1. ADVANCED_ECOMMERCE: Platform detected with tracking pixel
        self.assertEqual(
            classify_digital_maturity(0, "https://loja.com", "Shopify", True, True),
            "ADVANCED_ECOMMERCE"
        )
        # 2. BASIC_ECOMMERCE: Platform detected without tracking pixel
        self.assertEqual(
            classify_digital_maturity(0, "https://loja.com", "WooCommerce", True, False),
            "BASIC_ECOMMERCE"
        )
        # 3. INSTITUTIONAL_WEBSITE: Active domain without e-commerce cart/platform
        self.assertEqual(
            classify_digital_maturity(0, "https://loja.com", "None", False, False),
            "INSTITUTIONAL_WEBSITE"
        )
        # 4. NO_DIGITAL_PRESENCE: Neither domain nor e-commerce detected
        self.assertEqual(
            classify_digital_maturity(0, None, "None", False, False),
            "NO_DIGITAL_PRESENCE"
        )

    @patch("urllib.request.urlopen")
    def test_analyze_layer_3_mock_http(self, mock_urlopen):
        """Validates layer 3 HTTP fingerprint detection using mocked HTTP response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = (
            b"<html><head><script src='https://cdn.shopify.com/s/files/1.js'></script>"
            b"<script src='https://www.googletagmanager.com/gtm.js?id=GTM-123'></script></head>"
            b"<body><a href='/cart'>Ver Carrinho</a></body></html>"
        )
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        platform, has_cart, has_pixel = analyze_layer_3_http("https://www.lojamock.com.br")
        self.assertEqual(platform, "Shopify")
        self.assertTrue(has_cart)
        self.assertTrue(has_pixel)

    def test_filter_by_digital_maturity(self):
        """Validates company querying filtered by digital maturity."""
        company_offline = {
            "cnpj": "99999999000199",
            "legal_name": "LOJA SEM SITE LTDA",
            "trade_name": "Loja Sem Site",
            "primary_cnae": "4781400",
            "city": "LONDRINA",
            "digital_maturity": "NO_DIGITAL_PRESENCE",
        }
        company_online = {
            "cnpj": "88888888000188",
            "legal_name": "LOJA DIGITAL LTDA",
            "trade_name": "Loja Digital",
            "primary_cnae": "4781400",
            "city": "LONDRINA",
            "digital_maturity": "ADVANCED_ECOMMERCE",
        }
        insert_company(company_offline, db_path=self.test_db)
        insert_company(company_online, db_path=self.test_db)

        leads = list_companies(digital_maturity="NO_DIGITAL_PRESENCE", db_path=self.test_db)
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["cnpj"], "99999999000199")

    def test_generate_html_dashboard(self):
        """Validates generation of standalone interactive HTML dashboard."""
        company = {
            "cnpj": "12345678000195",
            "legal_name": "TESTE MODA LONDRINA LTDA",
            "trade_name": "Teste Moda",
            "primary_cnae": "4781400",
            "city": "LONDRINA",
            "phone": "43999112233",
            "digital_maturity": "NO_DIGITAL_PRESENCE",
        }
        insert_company(company, db_path=self.test_db)

        generated_file = generate_html_dashboard(
            db_path=self.test_db,
            output_path=self.test_html,
            auto_open=False,
        )
        self.assertTrue(generated_file.exists())
        content = generated_file.read_text(encoding="utf-8")
        self.assertIn("Painel de Prospecção Comercial", content)
        self.assertIn("Teste Moda", content)
        self.assertIn("12.345.678/0001-95", content)
        self.assertIn("wa.me/5543999112233", content)


if __name__ == "__main__":
    unittest.main()
