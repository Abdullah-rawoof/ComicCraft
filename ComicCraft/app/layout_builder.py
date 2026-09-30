import re
import logging

logger = logging.getLogger(__name__)

def _parse_panel_story(story_segment: str) -> dict:
    """Extract caption, narration, and dialogue components from a panel's story text."""
    caption = ""
    narration = ""
    dialogue = ""

    lines = story_segment.strip().split("\n")
    cleaned_lines = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        
        lower_line = line_clean.lower()
        if lower_line.startswith("caption:"):
            caption = line_clean[len("caption:"):].strip()
        elif lower_line.startswith("narration:"):
            narration = line_clean[len("narration:"):].strip()
        elif lower_line.startswith("dialogue:"):
            dialogue = line_clean[len("dialogue:"):].strip()
        elif not lower_line.startswith("[panel") and not lower_line.startswith("panel "):
            cleaned_lines.append(line_clean)

    # If narration wasn't explicitly tagged with "Narration:", assemble untagged lines
    if not narration and cleaned_lines:
        narration = " ".join(cleaned_lines)
    
    # If story has full combined text
    full_text = story_segment.strip()
    return {
        "caption": caption,
        "narration": narration,
        "dialogue": dialogue,
        "story": full_text
    }

def build_comic_layout(image_paths: list[str], full_story: str, outline: list[dict]) -> list[dict]:
    """
    Organize comic panels into a unified layout structure.
    Pairs each panel's outline info with its generated image and story narration.
    """
    logger.info("Building comic layout structure...")
    layout = []

    # Attempt to split full_story into panels
    # Handles: [Panel 1...], Panel 1: ..., **Panel 1**
    raw_segments = re.split(r'(?i)(?:\[\s*Panel\s*\d+[^\]]*\]|(?:\*\*|\#\#)?\s*Panel\s*\d+\s*[:\-–])', full_story)
    # The first element before the first Panel header might be empty or preamble
    story_blocks = [s.strip() for s in raw_segments if s.strip()]

    # If splitting didn't yield enough blocks, split by double newlines or fallback
    if len(story_blocks) < len(outline):
        alt_blocks = [b.strip() for b in full_story.split("\n\n") if b.strip()]
        if len(alt_blocks) >= len(outline):
            story_blocks = alt_blocks

    for idx, item in enumerate(outline):
        panel_num = item.get("panel", idx + 1)
        title = item.get("title", f"Panel {panel_num}")
        scene_desc = item.get("scene_description", "")
        img_prompt = item.get("image_prompt", "")

        # Safe image path retrieval
        img_path = image_paths[idx] if idx < len(image_paths) else ""
        web_image_path = img_path if img_path.startswith("/") else f"/{img_path}"

        # Match story block
        parsed = {"caption": "", "narration": "", "dialogue": "", "story": ""}
        if idx < len(story_blocks):
            parsed = _parse_panel_story(story_blocks[idx])
        
        # Ensure narration exists
        if not parsed["narration"]:
            parsed["narration"] = scene_desc or f"Action unfolds as the story of panel {panel_num} continues."
        if not parsed["story"]:
            parsed["story"] = f"Narration: {parsed['narration']}\nDialogue: {parsed.get('dialogue', '')}"

        layout.append({
            "panel": panel_num,
            "title": title,
            "image_path": web_image_path,
            "local_image_path": img_path,
            "scene_description": scene_desc,
            "image_prompt": img_prompt,
            "story": parsed["story"],
            "caption": parsed["caption"],
            "narration": parsed["narration"],
            "dialogue": parsed["dialogue"]
        })

    logger.info(f"Built comic layout with {len(layout)} panels.")
    return layout
