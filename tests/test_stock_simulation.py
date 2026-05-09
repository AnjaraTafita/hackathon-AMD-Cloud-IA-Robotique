import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app import (
    adjust_stock,
    confirm_delivery,
    find_article,
    load_inventory,
    prepare_selection,
)
from llm_assistant import build_pharmacist_context
from vision import process_image


class StockSimulationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "pharmacy.sqlite"
        self.inventory = load_inventory(self.db_path)

    def test_find_article_by_id(self):
        article = find_article(self.inventory, "MED-001")

        self.assertIsNotNone(article)
        self.assertEqual(article.nom, "Paracetamol 500mg")

    def test_find_article_by_unique_partial_name(self):
        article = find_article(self.inventory, "amoxicilline")

        self.assertIsNotNone(article)
        self.assertEqual(article.id_unique, "MED-003")

    def test_prepare_selection_success(self):
        result = prepare_selection(self.inventory, "MED-002", 2)

        self.assertTrue(result.ok)
        self.assertEqual(result.code, "SELECTION_OK")
        self.assertIn("Robot allant au compartiment: Rayon A2", result.messages)

    def test_prepare_selection_rejects_unknown_article(self):
        result = prepare_selection(self.inventory, "Produit inexistant", 1)

        self.assertFalse(result.ok)
        self.assertEqual(result.code, "ARTICLE_INTROUVABLE")

    def test_prepare_selection_rejects_insufficient_stock(self):
        result = prepare_selection(self.inventory, "MED-003", 999)

        self.assertFalse(result.ok)
        self.assertEqual(result.code, "STOCK_INSUFFISANT")

    def test_prepare_selection_rejects_invalid_quantity(self):
        result = prepare_selection(self.inventory, "MED-003", 0)

        self.assertFalse(result.ok)
        self.assertEqual(result.code, "QUANTITE_INVALIDE")

    def test_vision_integration_point_is_explicitly_disabled(self):
        result = process_image("images/paracetamol_500mg.svg")

        self.assertFalse(result.enabled)
        self.assertIn("Module vision non configure", result.message)

    def test_llm_context_keeps_pharmacist_validation(self):
        context = build_pharmacist_context("fievre et douleur", self.inventory)
        text = context.as_text()

        self.assertIn("assistant pour pharmacien", text)
        self.assertIn("fievre et douleur", text)
        self.assertIn("Ne pas delivrer automatiquement", text)

    def test_confirm_delivery_updates_sqlite_stock(self):
        result = confirm_delivery("MED-001", 2, self.db_path)
        inventory = load_inventory(self.db_path)
        article = find_article(inventory, "MED-001")

        self.assertTrue(result.ok)
        self.assertEqual(result.code, "LIVRAISON_CONFIRMEE")
        self.assertIsNotNone(article)
        self.assertEqual(article.quantite_stock, 118)

    def test_adjust_stock_can_add_and_remove(self):
        add_result = adjust_stock("MED-002", 5, "ajouter", self.db_path)
        remove_result = adjust_stock("MED-002", 3, "retirer", self.db_path)
        inventory = load_inventory(self.db_path)
        article = find_article(inventory, "MED-002")

        self.assertTrue(add_result.ok)
        self.assertTrue(remove_result.ok)
        self.assertIsNotNone(article)
        self.assertEqual(article.quantite_stock, 82)


if __name__ == "__main__":
    unittest.main()
