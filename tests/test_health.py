import sys
from pathlib import Path

# Add backend directory to sys.path so we can import main
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check_returns_200_and_ok():
    """Verify that GET /health returns status code 200 and VoiceMedic AI status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["system"] == "VoiceMedic AI"
