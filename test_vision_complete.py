"""
Complete test script for vision API with real images
"""
import requests
import os
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("\n" + "="*60)
    print("TEST 1: Health Check")
    print("="*60)
    
    response = requests.get(f"{BASE_URL}/vision/health", timeout=10)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(json.dumps(data, indent=2))
    return response.status_code == 200

def test_descriptors():
    """Test descriptors endpoint"""
    print("\n" + "="*60)
    print("TEST 2: Get Medical Descriptors")
    print("="*60)
    
    response = requests.get(f"{BASE_URL}/vision/descriptors", timeout=10)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Total descriptors: {data.get('total_descriptors')}")
    print(f"Categories: {list(data.get('categories', {}).keys())}")
    
    # Show sample
    if data.get('sample_descriptors'):
        print("\nSample descriptors:")
        for key, value in list(data.get('sample_descriptors', {}).items())[:5]:
            print(f"  {key}: {value}")
    
    return response.status_code == 200

def test_analyze_image(image_path):
    """Test image analysis"""
    print("\n" + "="*60)
    print(f"TEST 3: Analyze Image - {Path(image_path).name}")
    print("="*60)
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return False
    
    with open(image_path, 'rb') as f:
        files = {'file': (Path(image_path).name, f, 'image/jpeg')}
        data = {'top_k': '5'}
        
        response = requests.post(
            f"{BASE_URL}/vision/analyze",
            files=files,
            data=data,
            timeout=30
        )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nTop {len(result['top_matches'])} matches:")
        for match in result['top_matches']:
            print(f"  • {match['descriptor_text']}: {match['confidence']:.1%} confidence")
        
        print(f"\nModel: {result['model_info']['model']}")
        print(f"Total descriptors checked: {result['total_descriptors_checked']}")
        return True
    else:
        print(f"Error: {response.text}")
        return False

def test_custom_labels(image_path):
    """Test custom label analysis"""
    print("\n" + "="*60)
    print(f"TEST 4: Custom Labels - {Path(image_path).name}")
    print("="*60)
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return False
    
    custom_labels = "bright red color, pale skin, dark brown spot, yellow tint, normal healthy tissue"
    
    with open(image_path, 'rb') as f:
        files = {'file': (Path(image_path).name, f, 'image/jpeg')}
        data = {
            'labels': custom_labels,
            'top_k': '3'
        }
        
        response = requests.post(
            f"{BASE_URL}/vision/analyze-custom",
            files=files,
            data=data,
            timeout=30
        )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nCustom labels used: {custom_labels}")
        print(f"\nTop {len(result['top_matches'])} matches:")
        for match in result['top_matches']:
            print(f"  • {match['descriptor_text']}: {match['confidence']:.1%} confidence")
        return True
    else:
        print(f"Error: {response.text}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("VISION API COMPREHENSIVE TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test 1: Health
    try:
        results.append(("Health Check", test_health()))
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        results.append(("Health Check", False))
    
    # Test 2: Descriptors
    try:
        results.append(("Descriptors", test_descriptors()))
    except Exception as e:
        print(f"❌ Descriptors failed: {e}")
        results.append(("Descriptors", False))
    
    # Test 3 & 4: Image analysis (if test images exist)
    test_image = "test_images/red_inflamed.jpg"
    
    if os.path.exists(test_image):
        try:
            results.append(("Image Analysis", test_analyze_image(test_image)))
        except Exception as e:
            print(f"❌ Image analysis failed: {e}")
            results.append(("Image Analysis", False))
        
        try:
            results.append(("Custom Labels", test_custom_labels(test_image)))
        except Exception as e:
            print(f"❌ Custom labels failed: {e}")
            results.append(("Custom Labels", False))
    else:
        print(f"\n⚠️  No test images found. Run 'python create_test_images.py' first")
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")
    
    if total_passed == len(results):
        print("\n🎉 All tests passed! Vision API is fully operational!")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
