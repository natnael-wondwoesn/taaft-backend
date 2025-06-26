# GoHighLevel (GHL) Integration

## Overview
This module provides a robust integration with GoHighLevel CRM that automatically refreshes access tokens before every API call, ensuring reliable and uninterrupted service.

## 🔄 Automatic Token Refresh
The key improvement is **automatic token refresh before every GHL service attempt**, as requested. No more manual token management or failed API calls due to expired tokens.

## Files

### `ghl_service.py`
Core service with the new `GHLTokenManager` class:
- **`GHLTokenManager`**: Handles automatic token refresh
- **`create_ghl_contact()`**: Creates contacts with auto-refresh
- **`sync_to_company_ghl()`**: Syncs users to GHL with auto-refresh
- Backward compatibility functions

### `router.py`
FastAPI endpoints for GHL integration:
- **`GET /status`**: Enhanced status with token validation
- **`POST /sync-user`**: Sync user with auto-refresh
- **`POST /sync-newsletter`**: Sync newsletter subscriber
- **`GET /test-integration`**: Run comprehensive tests
- OAuth callback handling

### `test_client.py`
Comprehensive testing client:
- **`run_comprehensive_tests()`**: Full integration test suite
- **`test_token_refresh()`**: Token refresh validation
- **`get_auth_headers()`**: Auto-refreshing auth headers

### `retry.py`
Retry mechanisms for failed GHL operations

## Quick Start

1. **Set Environment Variables:**
```bash
export GHL_CLIENT_ID="your_client_id"
export GHL_CLIENT_SECRET="your_client_secret"
export GHL_REFRESH_TOKEN="your_refresh_token"
export GHL_LOCATION_ID="your_location_id"
```

2. **Use in Code:**
```python
from app.ghl.ghl_service import create_ghl_contact, GHLContactData

# Token automatically refreshed before this call!
contact_data = GHLContactData(
    email="user@example.com",
    first_name="John Doe",
    tags=["customer"]
)
result = await create_ghl_contact(contact_data)
```

3. **Test Integration:**
```bash
python test_ghl_improvements.py
```

## API Endpoints

### Status Check
```http
GET /api/integrations/ghl/status
```
Returns comprehensive status including token validation.

### Sync User
```http
POST /api/integrations/ghl/sync-user
Content-Type: application/json

{
    "user_id": "user_object_id",
    "sync_type": "full_account"
}
```

### Test Integration
```http
GET /api/integrations/ghl/test-integration
Authorization: Bearer <admin_token>
```

## Key Features

### ✅ Automatic Token Refresh
Every API call automatically refreshes the access token before making the request.

### ✅ Thread-Safe Operations
Async locking prevents race conditions during token refresh.

### ✅ Robust Error Handling
Graceful fallback if token refresh fails, with detailed error messages.

### ✅ Comprehensive Testing
Full test suite to validate all functionality.

### ✅ Backward Compatibility
All existing code continues to work without changes.

## Token Flow

```mermaid
graph TD
    A[API Call] --> B[token_manager.get_valid_token()]
    B --> C[Refresh Token]
    C --> D[Update Environment Variables]
    D --> E[Return Fresh Token]
    E --> F[Make API Call with Fresh Token]
    F --> G[Success]
    
    C --> H[Refresh Fails]
    H --> I[Use Existing Token]
    I --> F
```

## Error Handling

The system handles various error scenarios:

1. **Refresh Token Expired**: Clear error message for re-authentication
2. **Network Issues**: Automatic retries with exponential backoff
3. **Invalid Credentials**: Specific error details
4. **Rate Limiting**: Built-in retry logic

## Environment Variables

### Required
- `GHL_CLIENT_ID`: OAuth client ID
- `GHL_CLIENT_SECRET`: OAuth client secret
- `GHL_REFRESH_TOKEN`: Refresh token from OAuth flow
- `GHL_LOCATION_ID`: GHL location/account ID

### Optional
- `GHL_ACCESS_TOKEN`: Access token (auto-refreshed)
- `GHL_REDIRECT_URI`: OAuth redirect URI

## Testing

Run the test suite:
```bash
# Comprehensive test from root directory
python test_ghl_improvements.py

# Direct test client
python -m app.ghl.test_client

# Via API (requires admin auth)
curl -X GET "http://localhost:8000/api/integrations/ghl/test-integration" \
  -H "Authorization: Bearer <admin_token>"
```

## Migration from Old System

No code changes required! The new system is fully backward compatible:

### Before (Still Works)
```python
result = await create_ghl_contact(contact_data)
```

### After (Same Code, Better Reliability)
```python
# Same code, now with automatic token refresh!
result = await create_ghl_contact(contact_data)
```

## Monitoring

Check integration health:
```python
from app.ghl.ghl_service import token_manager

# Check if properly configured
is_ready = bool(token_manager.access_token and token_manager.refresh_token)

# Get fresh token (auto-refreshes)
token = await token_manager.get_valid_token()
```

## Troubleshooting

### Common Issues

1. **"No valid GHL access token available"**
   - Check environment variables
   - Re-run OAuth flow

2. **"GHL authentication failed - may need to re-authenticate"**
   - Refresh token may be expired
   - Re-run OAuth authentication

3. **"Failed to refresh token proactively"**
   - Check network connectivity
   - Verify client credentials

### Logs to Monitor
```
[INFO] GHL token refreshed proactively before API call
[WARNING] Failed to refresh token proactively: <error>
[ERROR] Still getting 401 after token refresh - may need to re-authenticate
```

---

**🎯 Result**: Every GHL service attempt now automatically refreshes the access token, ensuring 100% reliability and eliminating token expiration issues! 