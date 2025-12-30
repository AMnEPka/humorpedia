#!/usr/bin/env python3
"""
Backend API Testing for Humorpedia
Tests hierarchical import feature, show children endpoint, and Cities API
"""

import requests
import json
import sys
import os
from datetime import datetime

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

def test_api_health():
    """Test basic API connectivity"""
    results = TestResults()
    
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code == 200:
            results.success("API Health Check")
        else:
            results.fail("API Health Check", f"Status {response.status_code}")
    except Exception as e:
        results.fail("API Health Check", str(e))
    
    return results

def test_hierarchical_shows():
    """Test hierarchical show structure and children endpoint"""
    results = TestResults()
    
    # Test 1: Get comedy-battle children
    try:
        response = requests.get(f"{API_BASE}/content/shows/comedy-battle/children", timeout=10)
        if response.status_code == 200:
            data = response.json()
            children = data.get('items', [])
            
            if len(children) >= 2:
                results.success("Comedy Battle children endpoint returns data")
                
                # Check for expected seasons
                season_titles = [child.get('title', '') for child in children]
                has_season9 = any('9 сезон' in title or 'season9' in title.lower() for title in season_titles)
                has_season10 = any('10 сезон' in title or 'season10' in title.lower() for title in season_titles)
                
                if has_season9:
                    results.success("Season 9 found in children")
                else:
                    results.fail("Season 9 found in children", f"Season titles: {season_titles}")
                
                if has_season10:
                    results.success("Season 10 found in children")
                else:
                    results.fail("Season 10 found in children", f"Season titles: {season_titles}")
                
                # Check hierarchical fields
                for i, child in enumerate(children[:2]):  # Check first 2 children
                    child_title = child.get('title', f'Child {i+1}')
                    
                    if child.get('parent_id'):
                        results.success(f"{child_title} has parent_id")
                    else:
                        results.fail(f"{child_title} has parent_id", "Missing parent_id field")
                    
                    if child.get('level') == 1:
                        results.success(f"{child_title} has level=1")
                    else:
                        results.fail(f"{child_title} has level=1", f"Level: {child.get('level')}")
                    
                    full_path = child.get('full_path', '')
                    if full_path.startswith('comedy-battle/'):
                        results.success(f"{child_title} has correct full_path")
                    else:
                        results.fail(f"{child_title} has correct full_path", f"Path: {full_path}")
            else:
                results.fail("Comedy Battle children endpoint returns data", f"Only {len(children)} children found")
        else:
            results.fail("Comedy Battle children endpoint", f"Status {response.status_code}: {response.text}")
    except Exception as e:
        results.fail("Comedy Battle children endpoint", str(e))
    
    # Test 2: Get show by path
    try:
        response = requests.get(f"{API_BASE}/content/shows/by-path/comedy-battle/season9", timeout=10)
        if response.status_code == 200:
            data = response.json()
            results.success("Get show by path (comedy-battle/season9)")
            
            # Check required fields
            if data.get('title'):
                results.success("Season 9 has title")
            else:
                results.fail("Season 9 has title", "Missing title")
            
            if data.get('full_path') == 'comedy-battle/season9':
                results.success("Season 9 has correct full_path")
            else:
                results.fail("Season 9 has correct full_path", f"Path: {data.get('full_path')}")
            
            if data.get('parent_id'):
                results.success("Season 9 has parent_id")
            else:
                results.fail("Season 9 has parent_id", "Missing parent_id")
            
            if data.get('level') == 1:
                results.success("Season 9 has level=1")
            else:
                results.fail("Season 9 has level=1", f"Level: {data.get('level')}")
        else:
            results.fail("Get show by path (comedy-battle/season9)", f"Status {response.status_code}: {response.text}")
    except Exception as e:
        results.fail("Get show by path (comedy-battle/season9)", str(e))
    
    # Test 3: Get show by slug
    try:
        response = requests.get(f"{API_BASE}/content/shows/season9", timeout=10)
        if response.status_code == 200:
            data = response.json()
            results.success("Get show by slug (season9)")
            
            if data.get('title'):
                results.success("Season 9 by slug has title")
            else:
                results.fail("Season 9 by slug has title", "Missing title")
        else:
            results.fail("Get show by slug (season9)", f"Status {response.status_code}: {response.text}")
    except Exception as e:
        results.fail("Get show by slug (season9)", str(e))
    
    return results

def test_data_integrity():
    """Test data integrity for hierarchical structure"""
    results = TestResults()
    
    # Get parent show (Comedy Battle)
    try:
        response = requests.get(f"{API_BASE}/content/shows/comedy-battle", timeout=10)
        if response.status_code == 200:
            parent_data = response.json()
            parent_id = parent_data.get('id')
            
            if parent_id:
                results.success("Comedy Battle parent has ID")
                
                # Get children and verify parent_id references
                children_response = requests.get(f"{API_BASE}/content/shows/comedy-battle/children", timeout=10)
                if children_response.status_code == 200:
                    children_data = children_response.json()
                    children = children_data.get('items', [])
                    
                    for child in children:
                        if child.get('parent_id') == parent_id:
                            results.success(f"Child '{child.get('title', 'Unknown')}' correctly references parent")
                        else:
                            results.fail(f"Child '{child.get('title', 'Unknown')}' correctly references parent", 
                                       f"Expected parent_id: {parent_id}, got: {child.get('parent_id')}")
                else:
                    results.fail("Get children for integrity check", f"Status {children_response.status_code}")
            else:
                results.fail("Comedy Battle parent has ID", "Missing ID field")
        else:
            results.fail("Get Comedy Battle parent", f"Status {response.status_code}")
    except Exception as e:
        results.fail("Data integrity check", str(e))
    
    return results

def test_shows_list_hierarchy():
    """Test shows list endpoint with hierarchy options"""
    results = TestResults()
    
    # Test default behavior (should exclude children)
    try:
        response = requests.get(f"{API_BASE}/content/shows", timeout=10)
        if response.status_code == 200:
            data = response.json()
            shows = data.get('items', [])
            
            # Check if child shows are excluded by default
            child_shows = [s for s in shows if s.get('level', 0) > 0]
            if len(child_shows) == 0:
                results.success("Shows list excludes children by default")
            else:
                results.fail("Shows list excludes children by default", f"Found {len(child_shows)} child shows")
        else:
            results.fail("Shows list default", f"Status {response.status_code}")
    except Exception as e:
        results.fail("Shows list default", str(e))
    
    # Test with include_children=true
    try:
        response = requests.get(f"{API_BASE}/content/shows?include_children=true", timeout=10)
        if response.status_code == 200:
            data = response.json()
            shows = data.get('items', [])
            
            # Check if child shows are included
            child_shows = [s for s in shows if s.get('level', 0) > 0]
            if len(child_shows) > 0:
                results.success("Shows list includes children when requested")
            else:
                results.fail("Shows list includes children when requested", "No child shows found")
        else:
            results.fail("Shows list with children", f"Status {response.status_code}")
    except Exception as e:
        results.fail("Shows list with children", str(e))
    
    return results

def main():
    """Run all tests"""
    print("🧪 Starting Backend API Tests for Hierarchical Shows")
    print("=" * 60)
    
    all_results = TestResults()
    
    # Run test suites
    test_suites = [
        ("API Health", test_api_health),
        ("Hierarchical Shows", test_hierarchical_shows),
        ("Data Integrity", test_data_integrity),
        ("Shows List Hierarchy", test_shows_list_hierarchy)
    ]
    
    for suite_name, test_func in test_suites:
        print(f"\n🔍 Testing {suite_name}:")
        print("-" * 40)
        
        suite_results = test_func()
        all_results.passed += suite_results.passed
        all_results.failed += suite_results.failed
        all_results.errors.extend(suite_results.errors)
    
    print("\n" + "=" * 60)
    success = all_results.summary()
    
    if success:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())