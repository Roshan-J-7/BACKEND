"""
Vision Client
CLIP model loader and inference engine for lightweight medical image analysis
"""

import torch
from PIL import Image
from typing import Optional, Dict, Any, List
import io
from transformers import CLIPProcessor, CLIPModel

from app.vision_model.vision_config import (
    VISION_MODEL_NAME,
    VISION_CACHE_DIR,
    VISION_DEVICE,
    MEDICAL_DESCRIPTORS,
    DESCRIPTOR_CATEGORIES,
    VISION_CONFIDENCE_THRESHOLD,
    VISION_MAX_MATCHES
)


class VisionClient:
    """Client for CLIP vision model inference"""
    
    def __init__(self):
        self.model_name = VISION_MODEL_NAME
        self.device = VISION_DEVICE
        self.cache_dir = VISION_CACHE_DIR
        
        # Model and processor (loaded lazily or on init)
        self.processor = None
        self.model = None
        self._is_loaded = False
        
        # Precomputed descriptor list
        self.descriptor_labels = list(MEDICAL_DESCRIPTORS.values())
        self.descriptor_keys = list(MEDICAL_DESCRIPTORS.keys())
    
    def load_model(self):
        """
        Load CLIP model and processor from Hugging Face.
        Downloads model on first run (~400 MB - much lighter than BLIP-2).
        
        Model is cached in ~/.cache/huggingface/ by default.
        DO NOT commit model files to git.
        """
        if self._is_loaded:
            print("[VISION] Model already loaded")
            return
        
        print(f"[VISION] Loading model: {self.model_name}")
        print(f"[VISION] Download size: ~400 MB (lightweight, AWS friendly)")
        print(f"[VISION] Cache location: {self.cache_dir or '~/.cache/huggingface/'}")
        
        try:
            # Load processor
            self.processor = CLIPProcessor.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir
            )
            
            # Load model - CPU friendly
            self.model = CLIPModel.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir
            )
            
            # Move to device (cpu/cuda)
            self.model.to(self.device)
            
            # Set to evaluation mode
            self.model.eval()
            
            self._is_loaded = True
            print(f"[VISION] ✅ CLIP model loaded successfully on {self.device}")
            print(f"[VISION] Ready with {len(self.descriptor_labels)} medical descriptors")
            
        except Exception as e:
            print(f"[VISION] ❌ Failed to load model: {str(e)}")
            raise RuntimeError(f"Vision model loading failed: {str(e)}")
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self._is_loaded
    
    def analyze_image(
        self,
        image: Image.Image,
        custom_labels: Optional[List[str]] = None,
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Analyze an image using CLIP similarity matching.
        
        Args:
            image: PIL Image object (RGB)
            custom_labels: Optional custom labels (defaults to MEDICAL_DESCRIPTORS)
            top_k: Number of top matches to return (defaults to VISION_MAX_MATCHES)
        
        Returns:
            Dict with matched descriptors and confidence scores
        """
        # Ensure model is loaded
        if not self._is_loaded:
            self.load_model()
        
        # Use default medical descriptors if not provided
        if custom_labels is None:
            labels = self.descriptor_labels
            label_keys = self.descriptor_keys
        else:
            labels = custom_labels
            label_keys = [f"custom_{i}" for i in range(len(labels))]
        
        # Use default top_k if not provided
        if top_k is None:
            top_k = VISION_MAX_MATCHES
        
        try:
            # Prepare inputs
            inputs = self.processor(
                text=labels,
                images=image,
                return_tensors="pt",
                padding=True
            )
            
            # Move inputs to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Run inference (no gradient calculation needed)
            with torch.no_grad():
                outputs = self.model(**inputs)
                
                # Compute similarity probabilities
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=1)[0]
            
            # Convert to CPU and numpy for processing
            probs_list = probs.cpu().tolist()
            
            # Create matches list
            matches = [
                {
                    "descriptor_key": label_keys[i],
                    "descriptor_text": labels[i],
                    "confidence": float(probs_list[i])
                }
                for i in range(len(labels))
            ]
            
            # Sort by confidence (descending)
            matches.sort(key=lambda x: x["confidence"], reverse=True)
            
            # Filter by confidence threshold
            filtered_matches = [
                m for m in matches
                if m["confidence"] >= VISION_CONFIDENCE_THRESHOLD
            ]
            
            # Take top K
            top_matches = filtered_matches[:top_k]
            
            # Group by category (for default medical descriptors)
            if custom_labels is None:
                categorized_matches = self._categorize_matches(top_matches)
            else:
                categorized_matches = {}
            
            return {
                "top_matches": top_matches,
                "categorized_matches": categorized_matches,
                "total_descriptors_checked": len(labels),
                "model_info": {
                    "model": self.model_name,
                    "device": self.device,
                    "confidence_threshold": VISION_CONFIDENCE_THRESHOLD
                }
            }
            
        except Exception as e:
            raise RuntimeError(f"Image analysis failed: {str(e)}")
    
    def _categorize_matches(self, matches: List[Dict]) -> Dict[str, List[Dict]]:
        """Group matches by category"""
        categorized = {}
        
        for match in matches:
            key = match["descriptor_key"]
            
            # Find category
            for category, keys in DESCRIPTOR_CATEGORIES.items():
                if key in keys:
                    if category not in categorized:
                        categorized[category] = []
                    categorized[category].append(match)
                    break
        
        return categorized
    
    def analyze_image_bytes(
        self,
        image_bytes: bytes,
        custom_labels: Optional[List[str]] = None,
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Analyze image from raw bytes.
        
        Args:
            image_bytes: Raw image bytes (JPEG, PNG, etc.)
            custom_labels: Optional custom labels
            top_k: Number of top matches to return
        
        Returns:
            Dict with matched descriptors and confidence scores
        """
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            
            # Analyze
            return self.analyze_image(image, custom_labels, top_k)
            
        except Exception as e:
            raise ValueError(f"Invalid image data: {str(e)}")
    
    def get_descriptor_info(self) -> Dict[str, Any]:
        """Get information about available descriptors"""
        return {
            "total_descriptors": len(MEDICAL_DESCRIPTORS),
            "categories": {
                category: len(keys)
                for category, keys in DESCRIPTOR_CATEGORIES.items()
            },
            "sample_descriptors": dict(list(MEDICAL_DESCRIPTORS.items())[:5])
        }
    
    def unload_model(self):
        """
        Unload model from memory (useful for testing/development).
        In production, keep model loaded for performance.
        """
        if self._is_loaded:
            del self.model
            del self.processor
            self.model = None
            self.processor = None
            self._is_loaded = False
            
            # Clear CUDA cache if using GPU
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            print("[VISION] Model unloaded from memory")


# Global vision client instance
vision_client = VisionClient()
