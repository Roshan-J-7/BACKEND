import requests
import json

# Test health endpoint
print("Testing vision API health endpoint...")
try:
    response = requests.get("http://localhost:8000/vision/health", timeout=5)
    print(f"\nStatus: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

# Test descriptors endpoint  
print("\n\nTesting vision API descriptors endpoint...")
try:
    response = requests.get("http://localhost:8000/vision/descriptors", timeout=5)
    print(f"\nStatus: {response.status_code}")
    data = response.json()
    print(f"Total descriptors: {data.get('total_descriptors')}")
    print(f"Categories: {len(data.get('categories', []))}")
    
    # Show first category
    if data.get('categories'):
        cat = data['categories'][0]
        print(f"\nFirst category: {cat['category']}")
        print(f"  Labels: {cat['labels'][:3]}...")
except Exception as e:
    print(f"Error: {e}")

print("\n\nDone!")
