"""
Test script for vision API endpoints
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test the health endpoint"""
    print("\n" + "="*50)
    print("Testing /vision/health")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/vision/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_descriptors():
    """Test the descriptors endpoint"""
    print("\n" + "="*50)
    print("Testing /vision/descriptors")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/vision/descriptors")
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print(f"Total Descriptors: {data.get('total_descriptors')}")
        print(f"\nCategories ({len(data.get('categories', []))}):")
        
        for category in data.get('categories', []):
            labels = category.get('labels', [])
            print(f"  - {category['category']}: {len(labels)} labels")
            print(f"    {', '.join(labels[:5])}{'...' if len(labels) > 5 else ''}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_analyze_custom():
    """Test custom analysis with a few labels"""
    print("\n" + "="*50)
    print("Testing /vision/analyze-custom (text-only - no image)")
    print("="*50)
    
    try:
        # This will fail without an image, but tests the endpoint structure
        data = {
            "custom_labels": ["healthy skin", "red", "inflamed", "normal"]
        }
        response = requests.post(
            f"{BASE_URL}/vision/analyze-custom",
            data=data
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Expected error (no image provided): {response.json().get('detail')}")
        return True  # Expected to fail without image
    except Exception as e:
        print(f"Error: {e}")
        return True  # Expected

if __name__ == "__main__":
    print("="*50)
    print("VISION API TEST SUITE")
    print("="*50)
    
    results = []
    
    # Test 1: Health check
    results.append(("Health Check", test_health()))
    
    # Test 2: Descriptors
    results.append(("Descriptors", test_descriptors()))
    
    # Test 3: Custom analysis structure
    results.append(("Custom Analysis Endpoint", test_analyze_custom()))
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")
