import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from url_shortener.app import create_app


class UrlShortenerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.temp_dir.name) / "links.sqlite3"))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_redirect_and_analytics(self) -> None:
        created = self.client.post("/v1/links", json={"url": "https://example.com/article"})
        self.assertEqual(created.status_code, 201)
        code = created.json()["code"]
        self.assertIn(f"/{code}", created.json()["short_url"])

        redirected = self.client.get(f"/{code}", follow_redirects=False)
        self.assertEqual(redirected.status_code, 302)
        self.assertEqual(redirected.headers["location"], "https://example.com/article")

        analytics = self.client.get(f"/v1/links/{code}/analytics")
        self.assertEqual(analytics.status_code, 200)
        self.assertEqual(analytics.json()["clicks"], 1)

    def test_invalid_url_is_rejected(self) -> None:
        response = self.client.post("/v1/links", json={"url": "not-a-url"})
        self.assertEqual(response.status_code, 422)

    def test_unknown_code_is_not_found(self) -> None:
        self.assertEqual(self.client.get("/missing", follow_redirects=False).status_code, 404)

    def test_health_is_a_bare_liveness_check(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_ready_confirms_database_connectivity(self) -> None:
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_responses_carry_a_request_id_header(self) -> None:
        response = self.client.get("/health")
        self.assertIn("x-request-id", {key.lower() for key in response.headers.keys()})

    def test_metrics_endpoint_exposes_prometheus_text_format(self) -> None:
        self.client.post("/v1/links", json={"url": "https://example.com/article"})

        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])
        self.assertIn("url_shortener_requests_total", response.text)
        self.assertIn("url_shortener_links_created_total", response.text)


if __name__ == "__main__":
    unittest.main()
