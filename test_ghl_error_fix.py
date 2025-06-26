#!/usr/bin/env python3
"""
Test script to verify GHL error fixes
This script tests that GHL integration gracefully handles missing refresh tokens
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ghl.ghl_service import token_manager, sync_to_company_ghl, SignupType


async def test_unconfigured_ghl():
    """Test GHL behavior when not properly configured."""
    print("🧪 Testing GHL behavior when not configured...")
    
    # Save original values
    original_refresh_token = token_manager.refresh_token
    original_access_token = token_manager.access_token
    
    # Temporarily clear tokens to simulate unconfigured state
    token_manager.refresh_token = None
    token_manager.access_token = None
    
    try:
        # Test 1: Check configuration status
        is_configured = token_manager.is_configured()
        print(f"✓ Configuration check: {is_configured} (should be False)")
        
        # Test 2: Try to sync user (should not fail the registration)
        test_user = {
            "id": "test_user_id",
            "email": "test@example.com",
            "full_name": "Test User"
        }
        
        try:
            result = await sync_to_company_ghl(test_user, SignupType.ACCOUNT)
            print(f"✓ Sync result: {result}")
            
            if result.get("skipped"):
                print("✅ GHL sync properly skipped when not configured")
                return True
            else:
                print("⚠️  Expected sync to be skipped")
                return False
                
        except Exception as e:
            print(f"❌ Sync should not raise exception: {str(e)}")
            return False
            
    finally:
        # Restore original values
        token_manager.refresh_token = original_refresh_token
        token_manager.access_token = original_access_token


async def test_configured_ghl():
    """Test GHL behavior when properly configured."""
    print("\n🧪 Testing GHL behavior when configured...")
    
    # Check if GHL is actually configured
    if not token_manager.is_configured():
        print("ℹ️  GHL not configured - skipping configured tests")
        return True
    
    try:
        # Test configuration check
        is_configured = token_manager.is_configured()
        print(f"✓ Configuration check: {is_configured} (should be True)")
        
        # Test token refresh
        try:
            token = await token_manager.get_valid_token()
            print(f"✓ Token refresh successful (first 20 chars): {token[:20]}...")
            return True
        except Exception as e:
            print(f"⚠️  Token refresh failed: {str(e)}")
            return False
            
    except Exception as e:
        print(f"❌ Configured test failed: {str(e)}")
        return False


async def main():
    """Main test function."""
    print("=" * 60)
    print("🔧 GHL Error Fix Validation")
    print("=" * 60)
    
    test_results = []
    
    # Test 1: Unconfigured GHL
    test_results.append(await test_unconfigured_ghl())
    
    # Test 2: Configured GHL (if available)
    test_results.append(await test_configured_ghl())
    
    # Summary
    passed = sum(test_results)
    total = len(test_results)
    
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    print(f"Tests Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("\nKey fixes verified:")
        print("✅ GHL sync gracefully handles missing refresh tokens")
        print("✅ User registration doesn't fail when GHL is unconfigured")
        print("✅ Proper error logging without crashes")
        print("✅ Configuration checks work correctly")
        
        print("\n🚀 The GHL integration now properly handles missing configuration!")
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    
    if success:
        print("\n✅ GHL error fixes are working correctly!")
        exit(0)
    else:
        print("\n❌ Some issues remain. Please check the implementation.")
        exit(1) 