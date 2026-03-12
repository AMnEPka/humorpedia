#!/usr/bin/env python3
"""
Focused MongoDB Connection Unification Smoke Test
Tests only the core endpoints to verify the unified database connection works
"""

import requests
import json
import sys

# Get backend URL from frontend .env
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"Error reading frontend .env: {e}")
        return None

BACKEND_URL = get_backend_url()
if not BACKEND_URL:
    print("❌ Could not get REACT_APP_BACKEND_URL from frontend/.env")
    sys.exit(1)

API_BASE = f"{BACKEND_URL}/api"
print(f"🔗 Testing API at: {API_BASE}")
print("🧪 MongoDB Connection Unification Smoke Test")
print("=" * 60)

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def success(self, test_name):
        self.passed += 1
        print(f"✅ {test_name}")
    
    def fail(self, test_name, error):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"❌ {test_name}: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n📊 Test Results: {self.passed}/{total} passed")
        if self.errors:
            print("\n🔍 Failed Tests:")
            for error in self.errors:
                print(f"  - {error}")
        return self.failed == 0

def main():
    results = TestResults()
    
    # Get auth token first
    access_token = None
    try:
        response = requests.post(f"{API_BASE}/auth/login", json={
            "email": "admin@humorpedia.local", 
            "password": "admin"
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            access_token = data.get('access_token')
            results.success("1. POST /api/auth/login → access_token")
        else:
            results.fail("1. POST /api/auth/login", f"Status {response.status_code}: {response.text}")
            return results.summary()
    except Exception as e:
        results.fail("1. POST /api/auth/login", str(e))
        return results.summary()
    
    # Test core endpoints from the review request
    test_endpoints = [
        # Basic health and stats
        ("2. GET /api/health", "GET", "/health", None, lambda d: d.get("status") == "healthy"),
        ("3. GET /api/stats", "GET", "/stats", None, lambda d: isinstance(d.get("people"), int) and isinstance(d.get("teams"), int)),
        
        # Auth endpoints with token
        ("4. GET /api/auth/me", "GET", "/auth/me", access_token, lambda d: "username" in d and "email" in d),
        ("5. POST /api/auth/refresh", "POST", "/auth/refresh", access_token, lambda d: "access_token" in d and "user" in d),
        
        # Content endpoints (should return valid responses even if empty)
        ("6. GET /api/content/people", "GET", "/content/people?limit=1", None, lambda d: "items" in d),
        ("7. GET /api/content/teams", "GET", "/content/teams?limit=1", None, lambda d: "items" in d),
        ("8. GET /api/content/shows", "GET", "/content/shows?limit=1", None, lambda d: "items" in d),
        ("9. GET /api/content/articles", "GET", "/content/articles?limit=1", None, lambda d: "items" in d),
        ("10. GET /api/content/news", "GET", "/content/news?limit=1", None, lambda d: "items" in d),
        
        # Special endpoints with trailing slash
        ("11. GET /api/sections/", "GET", "/sections/?limit=1", None, lambda d: "items" in d),
        ("12. GET /api/cities/", "GET", "/cities/?limit=1", None, lambda d: "items" in d),
        
        # Other endpoints
        ("13. GET /api/tags", "GET", "/tags?limit=1", None, lambda d: "items" in d),
        ("14. GET /api/templates", "GET", "/templates?limit=1", None, lambda d: "items" in d),
        ("15. GET /api/comments", "GET", "/comments?resource_type=article&resource_id=test&limit=1", access_token, lambda d: "items" in d or isinstance(d, list)),
    ]
    
    for test_name, method, endpoint, needs_auth, validator in test_endpoints:
        try:
            headers = {}
            if needs_auth and access_token:
                headers["Authorization"] = f"Bearer {access_token}"
            elif needs_auth and not access_token:
                results.fail(test_name, "No auth token available")
                continue
                
            if method == "POST":
                response = requests.post(f"{API_BASE}{endpoint}", headers=headers, timeout=10)
            else:
                response = requests.get(f"{API_BASE}{endpoint}", headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if validator(data):
                        results.success(f"{test_name} → valid response")
                    else:
                        results.fail(f"{test_name} → valid response", f"Invalid response structure: {data}")
                except json.JSONDecodeError:
                    results.fail(f"{test_name} → valid JSON", f"Response is not valid JSON")
            else:
                results.fail(test_name, f"Status {response.status_code}: {response.text[:200]}")
                
        except Exception as e:
            results.fail(test_name, str(e))
    
    print("\n" + "=" * 60)
    success = results.summary()
    
    if success:
        print("\n🎉 All MongoDB unification smoke tests passed!")
        print("✅ The unified get_db() function works correctly for all endpoints")
        return 0
    else:
        print("\n💥 Some smoke tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())