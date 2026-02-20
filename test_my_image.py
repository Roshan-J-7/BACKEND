"""
Test vision API with YOUR OWN medical images
Just drag and drop your image or provide the path
"""
import requests
import json
import sys
import os
from pathlib import Path

BASE_URL = "http://localhost:8000"

def analyze_my_image(image_path, top_k=5):
    """Analyze your medical image"""
    
    # Check if file exists
    if not os.path.exists(image_path):
        print(f"❌ ERROR: Image not found at: {image_path}")
        print(f"   Please check the path and try again.")
        return
    
    print("\n" + "="*70)
    print(f"📸 ANALYZING YOUR IMAGE: {Path(image_path).name}")
    print("="*70)
    
    # Upload and analyze
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (Path(image_path).name, f, 'image/jpeg')}
            data = {'top_k': str(top_k)}
            
            print(f"\n⏳ Uploading image to vision API...")
            print(f"   Server: {BASE_URL}/vision/analyze")
            print(f"   Top matches requested: {top_k}")
            
            response = requests.post(
                f"{BASE_URL}/vision/analyze",
                files=files,
                data=data,
                timeout=30
            )
        
        if response.status_code != 200:
            print(f"\n❌ ERROR: Server returned status {response.status_code}")
            print(f"   Response: {response.text}")
            return
        
        # Display results
        result = response.json()
        
        print(f"\n✅ ANALYSIS COMPLETE")
        print(f"\n{'='*70}")
        print(f"🎯 TOP {len(result['top_matches'])} MEDICAL MATCHES:")
        print(f"{'='*70}")
        
        for i, match in enumerate(result['top_matches'], 1):
            confidence_bar = "█" * int(match['confidence'] * 20)
            print(f"\n{i}. {match['descriptor_text'].upper()}")
            print(f"   Confidence: {match['confidence']:.1%}  {confidence_bar}")
        
        # Show categorized results
        if result.get('categorized_matches'):
            print(f"\n{'='*70}")
            print(f"📊 MATCHES BY MEDICAL CATEGORY:")
            print(f"{'='*70}")
            
            for category, matches in result['categorized_matches'].items():
                if matches:
                    print(f"\n{category.upper()}:")
                    for match in matches:
                        print(f"  • {match['descriptor_text']} ({match['confidence']:.1%})")
        
        print(f"\n{'='*70}")
        print(f"ℹ️  MODEL INFO:")
        print(f"{'='*70}")
        print(f"Model: {result['model_info']['model']}")
        print(f"Device: {result['model_info']['device']}")
        print(f"Total descriptors checked: {result['total_descriptors_checked']}")
        print(f"Confidence threshold: {result['model_info']['confidence_threshold']}")
        
        print(f"\n{'='*70}")
        print(f"✅ DONE!")
        print(f"{'='*70}\n")
        
    except requests.exceptions.Timeout:
        print(f"\n❌ ERROR: Request timed out. Is the server running?")
        print(f"   Start server with: uvicorn app.main:app --reload")
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Cannot connect to server at {BASE_URL}")
        print(f"   Make sure the server is running!")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")

def test_with_custom_labels(image_path, labels):
    """Test with your own custom descriptors"""
    
    if not os.path.exists(image_path):
        print(f"❌ ERROR: Image not found at: {image_path}")
        return
    
    print("\n" + "="*70)
    print(f"📸 CUSTOM ANALYSIS: {Path(image_path).name}")
    print("="*70)
    
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (Path(image_path).name, f, 'image/jpeg')}
            data = {
                'labels': labels,
                'top_k': '5'
            }
            
            print(f"\n⏳ Analyzing with custom labels...")
            print(f"   Labels: {labels}")
            
            response = requests.post(
                f"{BASE_URL}/vision/analyze-custom",
                files=files,
                data=data,
                timeout=30
            )
        
        if response.status_code != 200:
            print(f"\n❌ ERROR: {response.text}")
            return
        
        result = response.json()
        
        print(f"\n✅ RESULTS:")
        for i, match in enumerate(result['top_matches'], 1):
            print(f"{i}. {match['descriptor_text']}: {match['confidence']:.1%}")
        
        print(f"\n✅ DONE!\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🏥 MEDICAL IMAGE VISION ANALYZER")
    print("="*70)
    
    # Check if image path provided as argument
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        analyze_my_image(image_path)
    else:
        # Interactive mode
        print("\n📁 DRAG AND DROP YOUR IMAGE HERE (or paste the full path)")
        print("   Supported formats: JPG, PNG, BMP, TIFF")
        print("\nExamples:")
        print('   - "C:\\Users\\YourName\\Desktop\\skin_rash.jpg"')
        print('   - "D:\\Medical Images\\wound.png"')
        print('   - Or just drag the file into this terminal window')
        
        image_path = input("\n👉 Image path: ").strip()
        # Remove PowerShell drag-and-drop artifacts: & 'path' -> path
        if image_path.startswith("& '") and image_path.endswith("'"):
            image_path = image_path[3:-1]
        elif image_path.startswith('& "') and image_path.endswith('"'):
            image_path = image_path[3:-1]
        image_path = image_path.strip('"').strip("'")
        
        if not image_path:
            print("\n❌ No image path provided. Exiting.")
            sys.exit(1)
        
        # Ask for number of results
        try:
            top_k_input = input("\n👉 How many top matches to show? (default: 5): ").strip()
            top_k = int(top_k_input) if top_k_input else 5
        except:
            top_k = 5
        
        # Analyze
        analyze_my_image(image_path, top_k)
        
        # Ask if user wants custom analysis
        custom = input("\n❓ Want to test with custom labels? (y/n): ").strip().lower()
        if custom == 'y':
            labels = input("👉 Enter comma-separated labels (e.g., 'red wound, healthy skin, infection'): ").strip()
            if labels:
                test_with_custom_labels(image_path, labels)
