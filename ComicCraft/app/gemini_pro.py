import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def _generate_fallback_story(outline: list[dict]) -> str:
    """Generate vivid story text with captions and dialogues when Gemini Pro is unreachable."""
    story_parts = []
    for item in outline:
        p_num = item.get("panel", 1)
        title = item.get("title", f"Panel {p_num}")
        desc = item.get("scene_description", "")
        
        panel_text = (
            f"[{title}]\n"
            f"Caption: Under the shifting skies, every breath carried the weight of destiny.\n"
            f"Narration: {desc} Every footstep echoed with determination as the journey unfolded.\n"
            f'Dialogue: "We have come too far to turn back now," whispered the hero, steeling their resolve for whatever lies ahead.'
        )
        story_parts.append(panel_text)
    
    return "\n\n".join(story_parts)

def generate_story(outline: list[dict]) -> str:
    """
    Generate full comic story narration and character dialogue using Google Gemini Pro.
    Takes a 5-panel outline list and returns a formatted multi-panel story string.
    """
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        logger.warning("No GEMINI_API_KEY found in environment or .env. Using fallback story narration.")
        return _generate_fallback_story(outline)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Prepare outline summary for prompt
        outline_summary = []
        for p in outline:
            outline_summary.append(
                f"Panel {p.get('panel')}: {p.get('title')}\nScene Description: {p.get('scene_description')}"
            )
        formatted_outline = "\n\n".join(outline_summary)

        prompt = (
            "You are a master comic book writer renowned for captivating storytelling, snappy dialogue, and rich narration. "
            "Write the complete script for a 5-panel comic based on the following panel outline:\n\n"
            f"{formatted_outline}\n\n"
            "Format your response panel-by-panel clearly. For EACH of the 5 panels, use the following exact structure:\n"
            "[Panel X: Title]\n"
            "Caption: [Ambient scene setting or sound effects]\n"
            "Narration: [Engaging narrative describing the action, character motivation, and emotional beat]\n"
            "Dialogue: [Clear character speech in quotation marks]\n\n"
            "Make the dialogue punchy and memorable, with high dramatic tension or comedic timing matching the tone."
        )

        # Use active Gemini models in candidate order
        candidate_models = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-pro-latest", "gemini-1.5-pro", "gemini-1.5-flash"]
        story_text = ""
        for m_name in candidate_models:
            try:
                model = genai.GenerativeModel(m_name)
                response = model.generate_content(prompt)
                if response and response.text:
                    story_text = response.text
                    logger.info(f"Gemini Story succeeded using model: {m_name}")
                    break
            except Exception as m_err:
                logger.warning(f"Gemini story model {m_name} failed: {m_err}. Trying next...")

        if story_text and len(story_text.strip()) > 50:
            return story_text.strip()
        else:
            return _generate_fallback_story(outline)

    except Exception as e:
        logger.error(f"Error calling Gemini Pro for story: {e}. Falling back.")
        return _generate_fallback_story(outline)
