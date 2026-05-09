import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import web_app
from app import find_article, load_inventory


class WebAppTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.previous_db_path = web_app.DB_PATH
        self.db_path = Path(self.temp_dir.name) / "pharmacy.sqlite"
        web_app.DB_PATH = self.db_path
        web_app.app.config["TESTING"] = True
        self.client = web_app.app.test_client()

    def tearDown(self):
        web_app.DB_PATH = self.previous_db_path

    def test_dashboard_displays_inventory(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"PharmaStock", response.data)
        self.assertIn(b"Paracetamol", response.data)

    def test_select_displays_selection_result(self):
        response = self.client.post(
            "/select",
            data={"query": "MED-001", "quantity": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Selection validee", response.data)
        self.assertIn(b"Paracetamol", response.data)

    def test_sell_updates_stock(self):
        response = self.client.post(
            "/sell",
            data={"query": "MED-001", "quantity": "2"},
            follow_redirects=True,
        )
        article = find_article(load_inventory(self.db_path), "MED-001")

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(article)
        self.assertEqual(article.quantite_stock, 118)

    def test_adjust_updates_stock(self):
        response = self.client.post(
            "/adjust",
            data={
                "adjust_query": "MED-002",
                "adjust_quantity": "4",
                "operation": "ajouter",
            },
            follow_redirects=True,
        )
        article = find_article(load_inventory(self.db_path), "MED-002")

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(article)
        self.assertEqual(article.quantite_stock, 84)

    def test_assistant_displays_llm_context(self):
        response = self.client.post(
            "/assistant",
            data={"symptoms": "fievre et douleur"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"fievre et douleur", response.data)
        self.assertIn(b"SYSTEM PROMPT", response.data)

    def test_product_image_route_serves_svg(self):
        response = self.client.get("/images/paracetamol_500mg.svg")

        self.assertEqual(response.status_code, 200)
        self.assertIn("image/svg+xml", response.content_type)
        response.close()


if __name__ == "__main__":
    unittest.main()
