#!/usr/bin/env python3
"""
Demo script showing how to use the JWT authentication system.

This script demonstrates:
1. User registration
2. User login
3. Using JWT tokens for authenticated requests
4. Token refresh
5. Protected endpoint access

Run this script with the API server running:
    python scripts/demo_auth.py
"""

import asyncio
import httpx
import json
import sys
from typing import Dict, Optional


class AuthDemo:
    """Demo client for testing authentication endpoints."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers with current access token."""
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}
    
    async def register_user(self, user_data: Dict) -> Dict:
        """Register a new user."""
        print(f"🚀 Registering user: {user_data['email']}")
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/auth/register",
            json=user_data
        )
        
        if response.status_code == 201:
            data = response.json()
            print(f"✅ User registered successfully!")
            print(f"   Email: {data['user']['email']}")
            print(f"   Username: {data['user']['username']}")
            print(f"   Verification required: {data['verification_required']}")
            return data
        else:
            print(f"❌ Registration failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return {}
    
    async def login_user(self, email: str, password: str, remember_me: bool = False) -> Dict:
        """Login user and store tokens."""
        print(f"🔐 Logging in user: {email}")
        
        login_data = {
            "email": email,
            "password": password,
            "remember_me": remember_me
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/auth/login",
            json=login_data
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data["tokens"]["access_token"]
            self.refresh_token = data["tokens"]["refresh_token"]
            
            print(f"✅ Login successful!")
            print(f"   User: {data['user']['email']}")
            print(f"   Role: {data['user']['role']}")
            print(f"   Token expires in: {data['tokens']['expires_in']} seconds")
            return data
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return {}
    
    async def get_current_user(self) -> Dict:
        """Get current user profile."""
        print("👤 Getting current user profile...")
        
        response = await self.client.get(
            f"{self.base_url}/api/v1/auth/me",
            headers=self.get_auth_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ User profile retrieved!")
            print(f"   ID: {data['id']}")
            print(f"   Email: {data['email']}")
            print(f"   Full name: {data['full_name']}")
            print(f"   Subscription: {data['subscription_tier']}")
            print(f"   API calls today: {data['api_calls_today']}")
            return data
        else:
            print(f"❌ Failed to get user profile: {response.status_code}")
            print(f"   Error: {response.json()}")
            return {}
    
    async def update_user_profile(self, update_data: Dict) -> Dict:
        """Update user profile."""
        print("📝 Updating user profile...")
        
        response = await self.client.put(
            f"{self.base_url}/api/v1/auth/me",
            json=update_data,
            headers=self.get_auth_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Profile updated successfully!")
            print(f"   Updated fields: {list(update_data.keys())}")
            return data
        else:
            print(f"❌ Failed to update profile: {response.status_code}")
            print(f"   Error: {response.json()}")
            return {}
    
    async def refresh_access_token(self) -> Dict:
        """Refresh the access token."""
        print("🔄 Refreshing access token...")
        
        if not self.refresh_token:
            print("❌ No refresh token available")
            return {}
        
        refresh_data = {"refresh_token": self.refresh_token}
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/auth/refresh",
            json=refresh_data
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            print(f"✅ Token refreshed successfully!")
            print(f"   New token expires in: {data['expires_in']} seconds")
            return data
        else:
            print(f"❌ Token refresh failed: {response.status_code}")
            print(f"   Error: {response.json()}")
            return {}
    
    async def get_auth_status(self) -> Dict:
        """Get authentication status."""
        print("📊 Getting authentication status...")
        
        response = await self.client.get(
            f"{self.base_url}/api/v1/auth/status",
            headers=self.get_auth_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Auth status retrieved!")
            print(f"   Authenticated: {data['authenticated']}")
            print(f"   API quota remaining: {data['api_quota_remaining']}")
            print(f"   Subscription active: {data['subscription_active']}")
            return data
        else:
            print(f"❌ Failed to get auth status: {response.status_code}")
            return {}
    
    async def logout_user(self) -> Dict:
        """Logout the current user."""
        print("👋 Logging out user...")
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/auth/logout",
            headers=self.get_auth_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = None
            self.refresh_token = None
            print(f"✅ Logout successful!")
            print(f"   Message: {data['message']}")
            return data
        else:
            print(f"❌ Logout failed: {response.status_code}")
            return {}
    
    async def test_unauthenticated_access(self) -> Dict:
        """Test accessing protected endpoint without authentication."""
        print("🚫 Testing unauthenticated access to protected endpoint...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/auth/me")
        
        if response.status_code == 401:
            print("✅ Protected endpoint correctly denied access")
            return {"status": "correctly_denied"}
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            return {"status": "unexpected"}


async def main():
    """Run the authentication demo."""
    print("🚀 JWT Authentication System Demo")
    print("=" * 50)
    
    demo = AuthDemo()
    
    try:
        # Test data
        user_data = {
            "email": "demo@example.com",
            "password": "DemoPassword123!",
            "username": "demouser",
            "first_name": "Demo",
            "last_name": "User",
            "organization": "Demo Corp",
            "job_title": "Tester"
        }
        
        # 1. Test unauthenticated access
        print("\n1. Testing unauthenticated access")
        print("-" * 30)
        await demo.test_unauthenticated_access()
        
        # 2. Register user
        print("\n2. User Registration")
        print("-" * 30)
        await demo.register_user(user_data)
        
        # 3. Login user
        print("\n3. User Login")
        print("-" * 30)
        login_result = await demo.login_user(
            user_data["email"], 
            user_data["password"],
            remember_me=True
        )
        
        if not login_result:
            print("❌ Cannot continue demo without successful login")
            return
        
        # 4. Get current user profile
        print("\n4. Get Current User Profile")
        print("-" * 30)
        await demo.get_current_user()
        
        # 5. Update user profile
        print("\n5. Update User Profile")
        print("-" * 30)
        update_data = {
            "organization": "Updated Demo Corp",
            "job_title": "Senior Tester"
        }
        await demo.update_user_profile(update_data)
        
        # 6. Get auth status
        print("\n6. Get Authentication Status")
        print("-" * 30)
        await demo.get_auth_status()
        
        # 7. Refresh token
        print("\n7. Refresh Access Token")
        print("-" * 30)
        await demo.refresh_access_token()
        
        # 8. Logout
        print("\n8. User Logout")
        print("-" * 30)
        await demo.logout_user()
        
        # 9. Test access after logout
        print("\n9. Test Access After Logout")
        print("-" * 30)
        await demo.test_unauthenticated_access()
        
        print("\n✅ Demo completed successfully!")
        
    except httpx.ConnectError:
        print("❌ Cannot connect to the API server.")
        print("   Make sure the server is running on http://localhost:8000")
        print("   Start it with: uvicorn src.main:app --reload")
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
    finally:
        await demo.close()


if __name__ == "__main__":
    asyncio.run(main())