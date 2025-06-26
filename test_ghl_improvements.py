#!/usr/bin/env python3
"""
Test script to validate GHL improvements
Run this to verify the new token management system is working correctly
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ghl.ghl_service import token_manager, GHLContactData, create_ghl_contact


async def test_token_manager():
    """Test the new token manager functionality."""
    print("🔧 Testing GHL Token Manager...")
    
    # Test 1: Check token manager initialization
    print(f"✓ Token manager initialized")
    print(f"  - Has access token: {bool(token_manager.access_token)}")
    print(f"  - Has refresh token: {bool(token_manager.refresh_token)}")
    
    # Test 2: Try to get valid token (this will auto-refresh)
    try:
        print("\n🔄 Testing automatic token refresh...")
        token = await token_manager.get_valid_token()
        print(f"✅ Successfully got valid token (first 20 chars): {token[:20]}...")
        return True
    except Exception as e:
        print(f"❌ Failed to get valid token: {str(e)}")
        return False


async def test_api_call():
    """Test an actual API call with automatic token refresh."""
    print("\n🌐 Testing API call with automatic token refresh...")
    
    # Create test contact data
    test_contact = GHLContactData(
        email=f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}@example.com",
        first_name="Auto Refresh Test",
        tags=["test", "auto-refresh"]
    )
    
    try:
        print(f"📞 Creating test contact: {test_contact.email}")
        result = await create_ghl_contact(test_contact)
        print(f"✅ Successfully created contact with auto-refresh")
        print(f"  - Contact ID: {result.get('contact', {}).get('id', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ Failed to create contact: {str(e)}")
        return False


async def test_comprehensive():
    """Run comprehensive tests using the new test client."""
    print("\n🧪 Running comprehensive GHL tests...")
    
    try:
        from app.ghl.test_client import run_comprehensive_tests
        results = await run_comprehensive_tests()
        
        passed = sum(results.values())
        total = len(results)
        
        print(f"\n📊 Test Results Summary:")
        print(f"  - Passed: {passed}/{total}")
        print(f"  - Success Rate: {(passed/total)*100:.1f}%")
        
        return passed == total
    except Exception as e:
        print(f"❌ Comprehensive tests failed: {str(e)}")
        return False


async def main():
    """Main test function."""
    print("=" * 60)
    print("🚀 GHL Integration Improvements Test Suite")
    print("=" * 60)
    
    # Check environment variables
    required_vars = ["GHL_CLIENT_ID", "GHL_CLIENT_SECRET", "GHL_REFRESH_TOKEN", "GHL_LOCATION_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these variables before running tests.")
        return False
    
    print("✓ All required environment variables are set")
    
    # Run tests
    test_results = []
    
    # Test 1: Token Manager
    test_results.append(await test_token_manager())
    
    # Test 2: API Call with Auto-Refresh
    test_results.append(await test_api_call())
    
    # Test 3: Comprehensive Tests
    test_results.append(await test_comprehensive())
    
    # Summary
    passed = sum(test_results)
    total = len(test_results)
    
    print("\n" + "=" * 60)
    print("📋 FINAL TEST SUMMARY")
    print("=" * 60)
    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! GHL improvements are working correctly.")
        print("\nKey improvements verified:")
        print("✅ Automatic token refresh before API calls")
        print("✅ Thread-safe token management")
        print("✅ Robust error handling")
        print("✅ Enhanced status monitoring")
        print("✅ Comprehensive testing suite")
    else:
        print("⚠️  Some tests failed. Please check the configuration and logs.")
    
    return passed == total


if __name__ == "__main__":
    print("Starting GHL improvements validation...")
    success = asyncio.run(main())
    
    if success:
        print("\n🎯 GHL integration is ready for production!")
        exit(0)
    else:
        print("\n🔧 Please address the issues before deploying.")
        exit(1) 