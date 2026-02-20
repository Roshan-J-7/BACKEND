"""
Vision Model Configuration
CLIP settings for lightweight medical image analysis
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ─────────────────────────────
# CLIP Model Configuration
# ─────────────────────────────

# Model Selection - Lightweight, AWS free tier friendly
VISION_MODEL_NAME = "openai/clip-vit-base-patch32"  # ~400MB, fast, CPU-friendly

# Inference Settings
VISION_TEMPERATURE = 0.0  # Not used in CLIP similarity matching

# Medical Visual Descriptors (40 predefined options)
# CLIP matches images against these descriptions
MEDICAL_DESCRIPTORS = {
    # Skin Conditions - Color
    "redness": "red inflamed skin",
    "pale_skin": "pale or whitish skin",
    "darkened_skin": "darkened or hyperpigmented skin",
    "yellowing": "yellowish discoloration of skin",
    "bluish_tint": "bluish or cyanotic skin",
    
    # Skin Conditions - Texture
    "smooth_skin": "smooth normal skin texture",
    "rough_texture": "rough or scaly skin texture",
    "bumpy_texture": "bumpy or raised skin surface",
    "blistered": "blisters or fluid-filled bumps",
    "dry_flaky": "dry flaky peeling skin",
    
    # Patterns
    "circular_rash": "circular or ring-shaped rash",
    "scattered_spots": "scattered spots or patches on skin",
    "linear_pattern": "linear or streak pattern on skin",
    "widespread_rash": "widespread rash covering large area",
    "localized_rash": "small localized rash or lesion",
    
    # Wounds/Injuries
    "open_wound": "open wound or cut with visible tissue",
    "closed_wound": "healed or closed wound with scar",
    "bruising": "bruise or contusion with discoloration",
    "burn_injury": "burn injury with damaged skin",
    "abrasion": "scraped or abraded skin surface",
    
    # Specific Conditions
    "fungal_infection": "fungal skin infection appearance",
    "bacterial_infection": "infected skin with pus or drainage",
    "allergic_reaction": "allergic skin reaction with hives",
    "eczema_dermatitis": "eczema or dermatitis rash",
    "psoriasis": "psoriasis plaques with scaling",
    
    # Swelling/Inflammation
    "swollen_area": "swollen or edematous area",
    "inflammation": "red inflamed irritated skin",
    "no_swelling": "normal skin without swelling",
    
    # Borders/Edges
    "well_defined": "well-defined borders and edges",
    "irregular_border": "irregular or undefined borders",
    "raised_border": "raised or elevated border around lesion",
    
    # Severity Indicators
    "mild_condition": "mild skin condition with minimal changes",
    "moderate_condition": "moderate skin condition with visible changes",
    "severe_condition": "severe skin condition with significant damage",
    
    # Normal/Baseline
    "normal_skin": "normal healthy skin appearance",
    "healing_skin": "skin showing signs of healing",
    
    # Additional Features
    "crusted_surface": "crusted or scabbed surface",
    "weeping_lesion": "weeping or oozing lesion",
    "pigmentation_change": "change in skin pigmentation or color",
    "hair_loss_area": "area with hair loss or thinning"
}

# Group descriptors by category for structured responses
DESCRIPTOR_CATEGORIES = {
    "color": ["redness", "pale_skin", "darkened_skin", "yellowing", "bluish_tint"],
    "texture": ["smooth_skin", "rough_texture", "bumpy_texture", "blistered", "dry_flaky"],
    "pattern": ["circular_rash", "scattered_spots", "linear_pattern", "widespread_rash", "localized_rash"],
    "wounds": ["open_wound", "closed_wound", "bruising", "burn_injury", "abrasion"],
    "conditions": ["fungal_infection", "bacterial_infection", "allergic_reaction", "eczema_dermatitis", "psoriasis"],
    "inflammation": ["swollen_area", "inflammation", "no_swelling"],
    "borders": ["well_defined", "irregular_border", "raised_border"],
    "severity": ["mild_condition", "moderate_condition", "severe_condition"],
    "baseline": ["normal_skin", "healing_skin"],
    "features": ["crusted_surface", "weeping_lesion", "pigmentation_change", "hair_loss_area"]
}

# Cache directory (Hugging Face will use system default if not specified)
# Default: ~/.cache/huggingface/
VISION_CACHE_DIR = os.getenv("HF_CACHE_DIR", None)

# Device configuration
VISION_DEVICE = os.getenv("VISION_DEVICE", "cpu")  # "cpu" or "cuda"

# ─────────────────────────────
# Model Loading Settings
# ─────────────────────────────

# Load model on startup (recommended for production)
# Set to False to load on first request (saves startup time for dev)
VISION_LOAD_ON_STARTUP = os.getenv("VISION_LOAD_ON_STARTUP", "true").lower() == "true"

# Download timeout (seconds) - CLIP is much smaller (~400MB)
VISION_DOWNLOAD_TIMEOUT = 120  # 2 minutes, much faster than BLIP-2

# Confidence threshold for returning matches
VISION_CONFIDENCE_THRESHOLD = 0.15  # Return matches with >15% confidence

# Maximum number of top matches to return
VISION_MAX_MATCHES = 5

print(f"[VISION CONFIG] Model: {VISION_MODEL_NAME}")
print(f"[VISION CONFIG] Device: {VISION_DEVICE}")
print(f"[VISION CONFIG] Load on startup: {VISION_LOAD_ON_STARTUP}")
print(f"[VISION CONFIG] Medical descriptors: {len(MEDICAL_DESCRIPTORS)}")
