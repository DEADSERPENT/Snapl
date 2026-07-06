"""
Locust load test for Snapl.

Usage:
    pip install locust
    locust -f scripts/load_test.py --host http://localhost:8000

Then open http://localhost:8089 and configure users/ramp-up.

Alternatively, run headless:
    locust -f scripts/load_test.py --host http://localhost:8000 \
           --headless -u 50 -r 10 --run-time 60s
"""

from locust import HttpUser, between, task


SHORT_CODE = "1"  # pre-seeded; update after your first POST /shorten


class RedirectUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(9)
    def redirect(self):
        self.client.get(f"/{SHORT_CODE}", allow_redirects=False)

    @task(1)
    def shorten(self):
        self.client.post(
            "/shorten",
            json={"url": "https://example.com/load-test-path"},
        )
