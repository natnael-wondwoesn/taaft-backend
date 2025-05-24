import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from ..main import app

client = TestClient(app)

# ... existing code ...


@pytest.mark.asyncio
@patch("app.algolia.migrater.tools_to_algolia.main")
async def test_migrate_tools_to_algolia(mock_migration, admin_token):
    """Test the admin endpoint to migrate tools to Algolia."""
    # Setup mock
    mock_migration.return_value = None

    # Make request with admin token
    response = client.post(
        "/admin/migrate-tools-to-algolia",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Assert response
    assert response.status_code == 202
    assert "migration" in response.json()["message"].lower()

    # Verify migration function was called
    mock_migration.assert_called_once()


@pytest.mark.asyncio
async def test_migrate_tools_to_algolia_unauthorized(user_token):
    """Test that non-admin users cannot access the migration endpoint."""
    # Make request with regular user token
    response = client.post(
        "/admin/migrate-tools-to-algolia",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    # Assert unauthorized
    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()
