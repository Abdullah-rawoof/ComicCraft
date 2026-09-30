import os
import re
import hashlib
import logging
import urllib.parse
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

PANELS_DIR = Path("static/panels")
PANELS_DIR.mkdir(parents=True, exist_ok=True)

# Lazy-loaded local pipeline singleton to avoid reloading models on every call
_pipeline = None

def _sanitize_prompt(prompt: str) -> str:
    """Sanitize prompt string to create safe, concise filename with unique hash."""
    clean = re.sub(r'[^a-zA-Z0-9_-]', '_', prompt)
    clean = re.sub(r'_+', '_', clean).strip('_')
    slug = clean[:40] if clean else "comic_panel"
    prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()[:8]
    return f"panel_{slug}_{prompt_hash}.png"

def _generate_pillow_comic_fallback(prompt: str, output_path: str):
    """Generate a stylized comic placeholder image using Pillow when completely offline."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        width, height = 768, 768
        img = Image.new("RGB", (width, height), color=(20, 24, 38))
        draw = ImageDraw.Draw(img)

        # Dynamic comic gradient background
        for y in range(height):
            ratio = y / height
            r = int(24 + 40 * ratio)
            g = int(28 + 20 * ratio)
            b = int(48 + 60 * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Halftone / comic dots pattern
        dot_spacing = 24
        for x in range(10, width, dot_spacing):
            for y in range(10, height, dot_spacing):
                draw.ellipse([x, y, x + 3, y + 3], fill=(45, 55, 90))

        # Outer bold comic panel border
        border_width = 8
        draw.rectangle([16, 16, width - 16, height - 16], outline=(255, 215, 0), width=border_width)
        draw.rectangle([24, 24, width - 24, height - 24], outline=(0, 0, 0), width=3)

        # Action blast burst in center
        center_x, center_y = width // 2, height // 2 - 40
        burst_points = []
        import math
        num_spikes = 16
        for i in range(num_spikes * 2):
            angle = i * (math.pi / num_spikes)
            radius = 240 if (i % 2 == 0) else 150
            px = center_x + radius * math.cos(angle)
            py = center_y + radius * math.sin(angle)
            burst_points.append((px, py))
        draw.polygon(burst_points, fill=(255, 75, 75), outline=(255, 230, 80), width=4)

        # Inner comic dialogue box
        box_y1 = height - 210
        draw.rectangle([40, box_y1, width - 40, height - 40], fill=(255, 255, 255), outline=(0, 0, 0), width=4)
        draw.rectangle([44, box_y1 + 4, width - 44, height - 44], outline=(255, 215, 0), width=2)

        # Text banner
        font = None
        font_bold = None
        font_path = "static/fonts/DejaVuSans-Bold.ttf"
        font_reg_path = "static/fonts/DejaVuSans.ttf"
        if os.path.exists(font_path):
            try:
                font_bold = ImageFont.truetype(font_path, 28)
                font = ImageFont.truetype(font_reg_path, 18)
            except Exception:
                pass

        if not font_bold:
            font_bold = ImageFont.load_default()
            font = ImageFont.load_default()

        draw.text((60, box_y1 + 18), "COMICCRAFT ILLUSTRATION", fill=(0, 0, 0), font=font_bold)
        
        # Word wrap prompt snippet
        words = prompt.split()
        lines = []
        curr = ""
        for w in words[:25]:
            if len(curr) + len(w) > 48:
                lines.append(curr)
                curr = w + " "
            else:
                curr += w + " "
        if curr:
            lines.append(curr)
        
        draw_y = box_y1 + 55
        for line in lines[:3]:
            draw.text((60, draw_y), line.strip(), fill=(50, 50, 50), font=font)
            draw_y += 24

        img.save(output_path, "PNG")
        logger.info(f"Generated stylized comic panel placeholder at {output_path}")
    except Exception as e:
        logger.error(f"Pillow fallback failed: {e}")

def _try_diffusers_local(prompt: str, output_path: str) -> bool:
    """Attempt local Stable Diffusion pipeline execution."""
    global _pipeline
    try:
        import torch
        from diffusers import StableDiffusionPipeline

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model_id = os.getenv("STABLE_DIFFUSION_MODEL", "runwayml/stable-diffusion-v1-5")
        
        logger.info(f"Loading local diffusers model {model_id} on {device}...")
        if _pipeline is None:
            if device == "cuda":
                _pipeline = StableDiffusionPipeline.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16,
                    safety_checker=None
                ).to(device)
            else:
                _pipeline = StableDiffusionPipeline.from_pretrained(
                    model_id,
                    torch_dtype=torch.float32,
                    safety_checker=None,
                    low_cpu_mem_usage=True
                ).to("cpu")

        # Run inference with comic styling parameters
        steps = 25 if device == "cuda" else 15
        image = _pipeline(
            prompt=f"{prompt}, comic book illustration style, sharp inks, vibrant colors",
            num_inference_steps=steps,
            guidance_scale=7.5
        ).images[0]
        
        image.save(output_path)
        logger.info(f"Diffusers generated image successfully: {output_path}")
        return True
    except Exception as e:
        logger.warning(f"Diffusers local generation failed or not configured: {e}")
        return False

def _try_huggingface_api(prompt: str, output_path: str) -> bool:
    """Attempt to generate using Hugging Face Inference API with HF_API_KEY."""
    hf_token = os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN")
    if not hf_token:
        return False

    try:
        import requests
        api_url = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
        headers = {"Authorization": f"Bearer {hf_token}"}
        payload = {
            "inputs": f"{prompt}, high quality comic book style illustration, rich colors, graphic novel ink lines",
            "parameters": {"width": 512, "height": 512}
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=45)
        if response.status_code == 200 and response.headers.get("content-type", "").startswith("image"):
            with open(output_path, "wb") as f:
                f.write(response.content)
            logger.info(f"HuggingFace API generated image: {output_path}")
            return True
        else:
            logger.warning(f"HF API returned status {response.status_code}: {response.text[:100]}")
            return False
    except Exception as e:
        logger.warning(f"HF API request failed: {e}")
        return False

def _try_pollinations_ai(prompt: str, output_path: str) -> bool:
    """Fetch high quality AI comic illustration via Pollinations (fast & free SD/Flux backend)."""
    try:
        styled_prompt = f"{prompt}, graphic novel comic book style, bold ink lines, dynamic comic coloring, detailed"
        encoded = urllib.parse.quote(styled_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=768&nologo=true&seed={hash(prompt) % 100000}"
        
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ComicCraft/1.0 (Comic Generator App)"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            if len(data) > 2048:
                with open(output_path, "wb") as f:
                    f.write(data)
                logger.info(f"Pollinations AI generated image: {output_path}")
                return True
        return False
    except Exception as e:
        logger.warning(f"Pollinations AI image generation failed: {e}")
        return False

def generate_image(prompt: str) -> str:
    """
    Generate a comic-style image based on the prompt and save it to static/panels/.
    Returns the file path to the saved image (e.g. 'static/panels/panel_...png').
    """
    filename = _sanitize_prompt(prompt)
    output_path = os.path.join("static", "panels", filename).replace("\\", "/")

    # Check cache: If image already exists and is non-empty, return it immediately
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
        logger.info(f"Using cached comic panel: {output_path}")
        return output_path

    # Priority 1: Hugging Face API if HF_API_KEY is configured
    if os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN"):
        if _try_huggingface_api(prompt, output_path):
            return output_path

    # Priority 2: Local Diffusers Pipeline if explicitly enabled and GPU is available
    if os.getenv("USE_LOCAL_DIFFUSERS", "false").lower() == "true":
        if _try_diffusers_local(prompt, output_path):
            return output_path

    # Priority 3: Pollinations AI cloud generator (fast, beautiful Stable Diffusion/Flux comic art)
    if _try_pollinations_ai(prompt, output_path):
        return output_path

    # Priority 4: Offline procedural comic artwork generator via Pillow
    _generate_pillow_comic_fallback(prompt, output_path)
    return output_path
