import os
import json
import re
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def _clean_json_string(text: str) -> str:
    """Clean markdown code blocks and whitespace from JSON response."""
    text = text.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text

def _generate_fallback_outline(user_prompt: str) -> list[dict]:
    """Generate a high-quality contextual 5-panel outline if Gemini API is unreachable or key is missing."""
    logger.info("Using intelligent procedural fallback for comic outline...")
    
    # Extract character name / subject if present
    match = re.search(r"(?i)(?:main\s+)?character:\s*([^.,\n]+)", user_prompt)
    if match:
        subject = match.group(1).strip()
    elif "fox" in user_prompt.lower():
        subject = "Rusty the Brave Fox"
    elif "superhero" in user_prompt.lower() or "hero" in user_prompt.lower():
        subject = "The Guardian"
    elif "detective" in user_prompt.lower():
        subject = "Detective Vance"
    else:
        subject = "The Hero"

    return [
        {
            "panel": 1,
            "title": "Panel 1: The Call to Adventure",
            "scene_description": f"The story opens as {subject} stands poised at the edge of the uncharted territory, observing strange glowing anomalies in the distance.",
            "image_prompt": f"Comic book illustration of {subject} standing dramatically at the edge of an epic vista, mysterious glow in the distance, comic art style, dynamic lighting, high detail, bold lines, 8k"
        },
        {
            "panel": 2,
            "title": "Panel 2: Into the Unknown",
            "scene_description": f"{subject} journeys deeper into the mysterious surroundings, discovering ancient glyphs and forgotten ruins along the path.",
            "image_prompt": f"Comic book panel depicting {subject} navigating deep glowing environment, discovering ancient symbols and mysterious relics, cinematic angle, vibrant comic colors, rich ink shading"
        },
        {
            "panel": 3,
            "title": "Panel 3: The Sudden Peril",
            "scene_description": f"A sudden obstacle appears! Shadows twist and a mysterious rival or monster confronts {subject} in a tense standoff.",
            "image_prompt": f"Dramatic comic action sequence, {subject} confronting a formidable shadowy obstacle, intense facial expression, dynamic action pose, comic blast effects, high contrast lighting"
        },
        {
            "panel": 4,
            "title": "Panel 4: The Climax of Courage",
            "scene_description": f"Gathering inner strength and clever tactics, {subject} makes a daring move, unleashing a wave of energy to turn the tide of battle.",
            "image_prompt": f"Climatic comic book action panel, {subject} unleashing a brilliant radiant burst of power, swirling comic speedlines, dramatic superhero angle, vibrant neon energy, masterpiece"
        },
        {
            "panel": 5,
            "title": "Panel 5: Dawn of Victory",
            "scene_description": f"The danger recedes as dawn breaks over the horizon. {subject} stands triumphant, guardian of the newfound peace.",
            "image_prompt": f"Heroic comic conclusion panel, {subject} victorious under golden sunrise, inspiring cinematic composition, comic book style, warm colorful palette, peaceful triumphant atmosphere"
        }
    ]

def generate_outline(user_prompt: str) -> list[dict]:
    """
    Generate a structured 5-panel comic outline using Google Gemini Flash.
    Returns a list of 5 dictionaries, each containing:
      - 'panel': int
      - 'title': str
      - 'scene_description': str
      - 'image_prompt': str
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        logger.warning("No GEMINI_API_KEY found in environment or .env. Using fallback outline.")
        return _generate_fallback_outline(user_prompt)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # Use gemini-1.5-flash as specified in project documentation
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.7,
                "response_mime_type": "application/json"
            }
        )

        system_instruction = (
            "You are an expert comic book scriptwriter and storyboard director. "
            "Based on the user's comic prompt, create a structured 5-panel comic storyline outline. "
            "You must return ONLY a JSON array containing exactly 5 panel objects. "
            "Each object must strictly contain these keys:\n"
            "- panel (integer: 1 to 5)\n"
            "- title (string: e.g. 'Panel 1: The Quest Begins')\n"
            "- scene_description (string: atmospheric description of setting, mood, and character action)\n"
            "- image_prompt (string: vivid, detailed prompt for Stable Diffusion comic book illustration, including art style keywords, comic inks, dynamic lighting)"
        )

        response = model.generate_content(
            f"{system_instruction}\n\nUser Story Prompt: {user_prompt}"
        )

        raw_text = response.text or ""
        cleaned_json = _clean_json_string(raw_text)
        data = json.loads(cleaned_json)

        # Validate that data is a list of 5 dictionaries with necessary keys
        if isinstance(data, list) and len(data) >= 5:
            validated = []
            for idx, item in enumerate(data[:5], start=1):
                validated.append({
                    "panel": int(item.get("panel", idx)),
                    "title": str(item.get("title", f"Panel {idx}")),
                    "scene_description": str(item.get("scene_description", "")),
                    "image_prompt": str(item.get("image_prompt", f"Comic panel illustration {idx}"))
                })
            return validated
        elif isinstance(data, dict) and "panels" in data and isinstance(data["panels"], list):
            validated = []
            for idx, item in enumerate(data["panels"][:5], start=1):
                validated.append({
                    "panel": int(item.get("panel", idx)),
                    "title": str(item.get("title", f"Panel {idx}")),
                    "scene_description": str(item.get("scene_description", "")),
                    "image_prompt": str(item.get("image_prompt", f"Comic panel illustration {idx}"))
                })
            return validated
        else:
            logger.warning(f"Unexpected JSON format from Gemini Flash: {raw_text[:200]}")
            return _generate_fallback_outline(user_prompt)

    except Exception as e:
        logger.error(f"Error calling Gemini Flash for outline: {e}. Falling back.")
        return _generate_fallback_outline(user_prompt)
