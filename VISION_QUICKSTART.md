# 🚀 CLIP Vision Model - Quick Start Guide

## ✅ Installation Complete!

Your lightweight vision module is ready using CLIP (not BLIP-2). Perfect for AWS free tier!

---

## 📥 Step 1: Install Dependencies

Already installed! ✅ Verify:

```powershell
pip list | Select-String "torch|transformers|pillow"
```

If missing, install:

```powershell
pip install torch torchvision transformers pillow python-multipart
```

---

## 🔽 Step 2: Download CLIP Model

**Model:** `openai/clip-vit-base-patch32` (~400 MB, AWS-friendly!)

**Option A: Automatic Download (Recommended)**

Just start your server! The model downloads automatically:

```powershell
uvicorn app.main:app --reload
```

On first startup:
- Downloads  **openai/clip-vit-base-patch32** (~400 MB)
- Saves to `C:\Users\<YourName>\.cache\huggingface\`
- Takes 1-3 minutes

**Option B: Manual Pre-Download**

```powershell
python -c "from transformers import CLIPProcessor, CLIPModel; CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32'); CLIPModel.from_pretrained('openai/clip-vit-base-patch32')"
```

---

## 🎯 Step 3: Test the Vision API

### Start the Server

```powershell
uvicorn app.main:app --reload
```

### Check Health

```powershell
curl http://localhost:8000/vision/health
```

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_name": "openai/clip-vit-base-patch32",
  "device": "cpu",
  "total_descriptors": 40
}
```

### Get Available Descriptors

```powershell
curl http://localhost:8000/vision/descriptors
```

See 40 medical descriptors across 10 categories!

### Analyze an Image

```powershell
curl -X POST "http://localhost:8000/vision/analyze" `
  -F "file=@path\to\your\image.jpg" `
  -F "top_k=5"
```

**Or use Swagger UI:**
- Open: http://localhost:8000/docs
- Find `/vision/analyze`
- Upload image
- Get top 5 matching descriptors with confidence scores

---

## 🌐 Deployment to AWS - IMPORTANT!

### ❌ DO NOT Push Model to Git

The model is **~400 MB** and is **already excluded** in `.gitignore`.

### ✅ What Gets Pushed to Cloud

```
✅ app/vision_model/vision_config.py
✅ app/vision_model/vision_client.py
✅ app/vision_model/vision_routes.py
✅ requirements.txt
❌ ~/.cache/huggingface/ (NOT pushed)
```

### Cloud Deployment (Auto-Download)

1. Push code to GitHub
2. Deploy to AWS (EC2 t2.micro, Elastic Beanstalk, etc.)
3. Model downloads automatically on first startup (~1-3 min)
4. Model cached - subsequent startups instant

**✅ Works on AWS Free Tier:**
- t2.micro (1 GB RAM) ✅
- RAM usage: ~500-700 MB
- Startup time: ~1-3 min first time, <10 sec after

---

## 📊 How CLIP Works (vs BLIP-2)

### CLIP (What You're Using)

```
Image → Similarity Matching → Confidence Scores
```

**Returns:**
```json
{
  "top_matches": [
    {"descriptor_text": "circular or ring-shaped rash", "confidence": 0.42},
    {"descriptor_text": "red inflamed skin", "confidence": 0.38},
    {"descriptor_text": "fungal skin infection appearance", "confidence": 0.21}
  ]
}
```

**Advantages:**
- ✅ 400 MB (vs 3-5 GB)
- ✅ 1-3 sec inference (vs 30-60 sec)
- ✅ 500 MB RAM (vs 2-4 GB)
- ✅ Structured output
- ✅ Explainable
- ✅ Fast & deterministic

---

## 🎯 40 Medical Descriptors

Predefined descriptors across 10 categories:

1. **Color** (5): red, pale, darkened, yellowing, bluish  
2. **Texture** (5): smooth, rough, bumpy, blistered, dry/flaky  
3. **Pattern** (5): circular, scattered, linear, widespread, localized  
4. **Wounds** (5): open wound, closed wound, bruising, burn, abrasion  
5. **Conditions** (5): fungal, bacterial, allergic, eczema, psoriasis  
6. **Inflammation** (3): swollen, inflammation, no swelling  
7. **Borders** (3): well-defined, irregular, raised  
8. **Severity** (3): mild, moderate, severe  
9. **Baseline** (2): normal skin, healing skin  
10. **Features** (4): crusted, weeping, pigmentation change, hair loss

**See full list:** `app/vision_model/vision_config.py`

---

## ⚙️ Configuration Options

Edit `.env` file:

```env
# Vision Model Settings
VISION_DEVICE=cpu              # or "cuda" for GPU
VISION_LOAD_ON_STARTUP=true    # Auto-load on server start
HF_CACHE_DIR=/custom/path      # Custom cache location (optional)
```

---

## 🏆 Integration with Cerebras LLM

**Recommended Architecture:**

```
Image
  ↓
CLIP (similarity matching)
  ↓
Top 3-5 visual descriptors
  ↓
Cerebras LLM (explanation)
  ↓
User-friendly medical guidance
```

**Example:**
```python
# Get CLIP results
clip_result = vision_client.analyze_image(image)

# Build prompt for Cerebras
prompt = f"""
Based on visual analysis, the image shows:
{', '.join([m['descriptor_text'] for m in clip_result['top_matches'][:3]])}

Provide safe, non-diagnostic medical guidance.
"""

# Send to Cerebras LLM
llm_response = cerebras_client.generate(prompt)
```

---

## 📁 Where is the Model Stored?

### Local Development:
```
Windows: C:\Users\<YourName>\.cache\huggingface\hub\
Linux/Mac: ~/.cache/huggingface/hub/
```

### Cloud Deployment:
```
Container: /root/.cache/huggingface/ (inside container)
Custom: Set HF_CACHE_DIR environment variable
```

---

## 🧪 Quick Test Script

Save as `test_vision.py`:

```python
from PIL import Image
from app.vision_model.vision_client import vision_client

# Load model
print("Loading CLIP model...")
vision_client.load_model()
print("✅ Model loaded!")

# Create or load test image
image = Image.open("test_image.jpg")

# Analyze
result = vision_client.analyze_image(image, top_k=5)

print("\nTop matches:")
for match in result['top_matches']:
    print(f"  {match['descriptor_text']}: {match['confidence']:.2f}")
```

Run:
```powershell
python test_vision.py
```

---

## 🔍 Verify Installation

```powershell
# 1. Check dependencies
pip list | Select-String "torch|transformers|pillow"

# 2. Start server
uvicorn app.main:app --reload

# 3. Check health endpoint
curl http://localhost:8000/vision/health

# 4. View API docs
# Open: http://localhost:8000/docs
```

---

## 🐛 Troubleshooting

### Problem: Server won't start
**Solution:**
- Check all dependencies installed: `pip list`
- Set `VISION_LOAD_ON_STARTUP=false` in `.env` to skip auto-load
- Call `/vision/load-model` endpoint manually

### Problem: Model download is slow
**Solution:** Be patient (400 MB download). Use faster internet or pre-download manually.

### Problem: "Out of memory" error
**Solution:** 
- CLIP is lightweight, but if it happens:
- Close other applications
- Use t3.micro instead of t2.micro on AWS

---

## 🎉 You're Ready!

Your CLIP vision model is configured and ready to analyze medical images.

**Key Points:**
- ✅ 400 MB model (AWS free tier safe!)
- ✅ 40 predefined medical descriptors
- ✅ 1-3 sec inference on CPU
- ✅ Structured confidence scores
- ✅ No diagnosis, just visual matching
- ❌ Don't commit model to Git (excluded)
- ✅ Auto-downloads on cloud deploy

**Next Steps:**
1. Test with sample medical images
2. Customize descriptors in `vision_config.py`
3. Integrate with Cerebras LLM
4. Deploy to AWS free tier
5. Build kiosk/telemedicine UI

Need help? Check `app/vision_model/README.md`
