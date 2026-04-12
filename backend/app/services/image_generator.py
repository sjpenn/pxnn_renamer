"""Image generation for campaigns via Replicate SDXL.

Two modes:
- Replicate: REPLICATE_API_TOKEN is set → calls SDXL via Replicate API
- Fallback: No token → returns placeholder image URLs (https://placehold.co)
"""
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

import httpx

from ..core.config import settings
from ..database.models import Campaign

REPLICATE_MODEL = "stability-ai/sdxl"
REPLICATE_VERSION = "39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"  # SDXL 1.0


@dataclass
class ImageResult:
    prompt: str
    image_url: str
    aspect_ratio: str


def _build_prompts(campaign: Campaign, count: int = 4) -> List[dict]:
    """Generate image prompt descriptions from campaign brief."""
    audience = campaign.target_audience or "music producers"
    product = campaign.product_description or "music production tool"
    tone = campaign.tone or "authentic"

    base_context = f"Professional ad photo for {product}, targeting {audience}. Style: {tone}, modern, clean."

    prompt_templates = [
        f"{base_context} Close-up of hands on MPC drum pads in a dimly lit studio, neon accent lighting, cinematic.",
        f"{base_context} Producer working at a DAW workstation with studio monitors, warm ambient lighting, lifestyle photography.",
        f"{base_context} Abstract sound wave visualization with dark background and cyan/magenta neon gradients, digital art.",
        f"{base_context} Overhead shot of a beat-making setup: laptop, headphones, MIDI controller, vinyl records, flat lay.",
        f"{base_context} Urban studio environment with acoustic panels, mixing console, artist silhouette, moody lighting.",
    ]
    return [
        {"prompt": p, "aspect_ratio": "1:1"}
        for p in prompt_templates[:count]
    ]


def _via_replicate(prompt: str, aspect_ratio: str, api_token: str) -> Optional[str]:
    """Call Replicate SDXL API. Returns image URL or None on failure."""
    width, height = (1024, 1024)
    if aspect_ratio == "9:16":
        width, height = 768, 1344
    elif aspect_ratio == "16:9":
        width, height = 1344, 768

    with httpx.Client(timeout=120.0) as client:
        # Create prediction
        response = client.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Prefer": "wait",  # Replicate sync mode
            },
            json={
                "version": REPLICATE_VERSION,
                "input": {
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "num_outputs": 1,
                    "scheduler": "K_EULER",
                    "num_inference_steps": 25,
                    "guidance_scale": 7.5,
                },
            },
        )
        response.raise_for_status()
        data = response.json()

        # If sync mode worked, output is already there
        if data.get("status") == "succeeded" and data.get("output"):
            return data["output"][0] if isinstance(data["output"], list) else data["output"]

        # Otherwise poll (fallback for models that don't support Prefer: wait)
        get_url = data.get("urls", {}).get("get")
        if not get_url:
            return None

        for _ in range(30):  # up to 60 seconds
            time.sleep(2)
            poll = client.get(
                get_url,
                headers={"Authorization": f"Bearer {api_token}"},
            )
            poll.raise_for_status()
            poll_data = poll.json()
            if poll_data.get("status") == "succeeded" and poll_data.get("output"):
                output = poll_data["output"]
                return output[0] if isinstance(output, list) else output
            if poll_data.get("status") == "failed":
                return None

    return None


def _via_fallback(prompt: str, aspect_ratio: str) -> str:
    """Return a placehold.co URL."""
    sizes = {"1:1": "1024x1024", "9:16": "768x1344", "16:9": "1344x768"}
    size = sizes.get(aspect_ratio, "1024x1024")
    # URL-safe version of the prompt (first 40 chars)
    label = prompt[:40].replace(" ", "+")
    return f"https://placehold.co/{size}/0a0b0f/00f0ff?text={label}"


def generate_images(campaign: Campaign, count: int = 4) -> List[ImageResult]:
    """Generate images for a campaign. Uses Replicate if token set, else placeholders."""
    prompt_specs = _build_prompts(campaign, count)
    results = []

    api_token = settings.REPLICATE_API_TOKEN

    for spec in prompt_specs:
        prompt = spec["prompt"]
        ar = spec["aspect_ratio"]

        if api_token:
            try:
                url = _via_replicate(prompt, ar, api_token)
                if url:
                    results.append(ImageResult(prompt=prompt, image_url=url, aspect_ratio=ar))
                    continue
            except Exception as e:
                print(f"[image_generator] Replicate failed for prompt: {e}", file=sys.stderr)

        # Fallback
        results.append(ImageResult(
            prompt=prompt,
            image_url=_via_fallback(prompt, ar),
            aspect_ratio=ar,
        ))

    return results
