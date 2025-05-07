import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import OAuthProvider

client = TestClient(app)


@pytest.fixture
def mock_google_provider():
    with patch("app.auth.oauth.google") as mock_google:
        mock_google.authorize_redirect = MagicMock(
            return_value={"Location": "https://accounts.google.com/oauth"}
        )
        yield mock_google


@pytest.fixture
def mock_github_provider():
    with patch("app.auth.oauth.github") as mock_github:
        mock_github.authorize_redirect = MagicMock(
            return_value={"Location": "https://github.com/login/oauth"}
        )
        yield mock_github


@pytest.fixture
def mock_create_sso_user():
    with patch("app.auth.oauth.create_sso_user") as mock_func:
        # Return a mock user
        mock_user = MagicMock()
        mock_user.id = "user123"
        mock_user.service_tier = "free"
        mock_user.is_verified = True
        mock_func.return_value = mock_user
        yield mock_func


def test_google_login(mock_google_provider):
    response = client.get("/api/auth/sso/login/google", allow_redirects=False)
    assert response.status_code == 307
    mock_google_provider.authorize_redirect.assert_called_once()


def test_github_login(mock_github_provider):
    response = client.get("/api/auth/sso/login/github", allow_redirects=False)
    assert response.status_code == 307
    mock_github_provider.authorize_redirect.assert_called_once()


def test_invalid_provider():
    response = client.get("/api/auth/sso/login/invalid", allow_redirects=False)
    assert response.status_code == 400


@patch("app.auth.sso_router.google.authorize_access_token")
@patch("app.auth.sso_router.get_google_user")
def test_google_callback(mock_get_user, mock_authorize, mock_create_sso_user):
    # Mock token and user info
    mock_authorize.return_value = {"access_token": "test_token"}
    mock_user_data = {"email": "test@example.com", "id": "user123", "name": "Test User"}
    mock_get_user.return_value = (
        "test@example.com",
        "user123",
        "Test User",
        mock_user_data,
    )

    response = client.get("/api/auth/sso/callback/google", allow_redirects=False)
    assert response.status_code == 307  # Redirect
    assert "access_token=" in response.headers["location"]
    assert "refresh_token=" in response.headers["location"]

    # Verify user creation
    mock_create_sso_user.assert_called_once_with(
        "test@example.com",
        "google",
        "user123",
        "Test User",
        subscribeToNewsletter=False,
        provider_data=mock_user_data,
    )
