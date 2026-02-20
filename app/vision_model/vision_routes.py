"""
Vision API Routes
FastAPI endpoints for lightweight medical image analysis using CLIP
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.vision_model.vision_client import vision_client
from app.vision_model.vision_config import (
    MEDICAL_DESCRIPTORS,
    DESCRIPTOR_CATEGORIES,
    VISION_MAX_MATCHES
)

# Thread pool for CPU-bound operations
_executor = ThreadPoolExecutor(max_workers=2)


# Create router
router = APIRouter(prefix="/vision", tags=["Vision"])


# ─────────────────────────────
# Request/Response Models
# ─────────────────────────────

class MatchResult(BaseModel):
    """Single descriptor match result"""
    descriptor_key: str
    descriptor_text: str
    confidence: float


class AnalysisResponse(BaseModel):
    """Response for image analysis"""
    top_matches: List[MatchResult]
    categorized_matches: Dict[str, List[MatchResult]]
    total_descriptors_checked: int
    model_info: dict


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    model_loaded: bool
    model_name: str
    device: str
    total_descriptors: int


class DescriptorInfoResponse(BaseModel):
    """Descriptor information response"""
    total_descriptors: int
    categories: Dict[str, int]
    sample_descriptors: Dict[str, str]


# ─────────────────────────────
# API Endpoints
# ─────────────────────────────

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...),
    top_k: Optional[int] = Form(VISION_MAX_MATCHES)
):
    """
    Analyze a medical image using CLIP similarity matching.
    
    **How it works:**
    - Matches image against 40 predefined medical descriptors
    - Returns top matches with confidence scores
    - Fast (~1-3 seconds), lightweight (~500MB RAM)
    - AWS free tier friendly
    
    **Supported file types:** JPEG, PNG, BMP, TIFF
    
    **Returns:**
    - `top_matches`: Top K matched descriptors with confidence scores
    - `categorized_matches`: Matches grouped by medical category
    - `total_descriptors_checked`: Number of descriptors evaluated
    - `model_info`: Model metadata
    
    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/vision/analyze" \\
      -F "file=@rash.jpg" \\
      -F "top_k=5"
    ```
    """
    try:
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.content_type}. Must be an image."
            )
        
        # Read image bytes
        image_bytes = await file.read()
        
        # Validate file size (max 10 MB)
        max_size = 10 * 1024 * 1024  # 10 MB
        if len(image_bytes) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: 10 MB"
            )
        
        # Run analysis in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            vision_client.analyze_image_bytes,
            image_bytes,
            None,  # custom_labels (None = use medical descriptors)
            top_k
        )
        
        return AnalysisResponse(
            top_matches=result["top_matches"],
            categorized_matches=result["categorized_matches"],
            total_descriptors_checked=result["total_descriptors_checked"],
            model_info=result["model_info"]
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Image analysis failed: {str(e)}"
        )


@router.post("/analyze-custom")
async def analyze_with_custom_labels(
    file: UploadFile = File(...),
    labels: str = Form(...),  # Comma-separated list
    top_k: Optional[int] = Form(VISION_MAX_MATCHES)
):
    """
    Analyze image with custom descriptors (instead of predefined medical ones).
    
    **Parameters:**
    - `file`: Image file
    - `labels`: Comma-separated custom descriptors (e.g., "red rash, blue bruise, normal skin")
    - `top_k`: Number of top matches to return
    
    **Returns:** Top matching labels with confidence scores
    
    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/vision/analyze-custom" \\
      -F "file=@image.jpg" \\
      -F "labels=red circular rash,fungal infection,normal skin" \\
      -F "top_k=3"
    ```
    """
    try:
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.content_type}. Must be an image."
            )
        
        # Parse labels
        custom_labels = [label.strip() for label in labels.split(",")]
        
        if len(custom_labels) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one label required"
            )
        
        if len(custom_labels) > 100:
            raise HTTPException(
                status_code=400,
                detail="Maximum 100 custom labels allowed"
            )
        
        # Read image
        image_bytes = await file.read()
        
        # Run analysis in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            vision_client.analyze_image_bytes,
            image_bytes,
            custom_labels,
            top_k
        )
        
        return {
            "top_matches": result["top_matches"],
            "total_descriptors_checked": result["total_descriptors_checked"],
            "model_info": result["model_info"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@router.get("/descriptors", response_model=DescriptorInfoResponse)
async def get_descriptors():
    """
    Get information about available medical descriptors.
    
    **Returns:**
    - Total number of descriptors
    - Breakdown by category
    - Sample descriptors
    """
    info = vision_client.get_descriptor_info()
    return DescriptorInfoResponse(
        total_descriptors=info["total_descriptors"],
        categories=info["categories"],
        sample_descriptors=info["sample_descriptors"]
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check vision service health and model status.
    
    **Returns:**
    - `status`: "healthy" or "not_loaded"
    - `model_loaded`: True if CLIP is loaded in memory
    - `model_name`: Model identifier
    - `device`: cpu or cuda
    - `total_descriptors`: Number of medical descriptors
    """
    from app.vision_model.vision_config import VISION_MODEL_NAME, VISION_DEVICE
    
    is_loaded = vision_client.is_loaded()
    
    return HealthResponse(
        status="healthy" if is_loaded else "not_loaded",
        model_loaded=is_loaded,
        model_name=VISION_MODEL_NAME,
        device=VISION_DEVICE,
        total_descriptors=len(MEDICAL_DESCRIPTORS)
    )


@router.post("/load-model")
async def load_model():
    """
    Manually trigger model loading.
    
    Useful if `VISION_LOAD_ON_STARTUP=false` in config.
    First load will download ~400 MB from Hugging Face (much lighter than BLIP-2).
    """
    try:
        if vision_client.is_loaded():
            return {"status": "already_loaded", "message": "Model is already loaded"}
        
        vision_client.load_model()
        return {"status": "success", "message": "CLIP model loaded successfully (~400MB)"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load model: {str(e)}"
        )


@router.post("/unload-model")
async def unload_model():
    """
    Unload model from memory (dev/testing only).
    
    ⚠️ Do NOT use in production - model loading is slow.
    """
    try:
        if not vision_client.is_loaded():
            return {"status": "not_loaded", "message": "Model is not loaded"}
        
        vision_client.unload_model()
        return {"status": "success", "message": "Model unloaded from memory"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unload model: {str(e)}"
        )
