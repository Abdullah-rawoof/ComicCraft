import os
import logging
from typing import Optional
from fastapi import APIRouter, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.gemini_flash import generate_outline
from app.gemini_pro import generate_story
from app.image_generator import generate_image
from app.layout_builder import build_comic_layout
from app.exporters import save_pdf

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

class PromptRequest(BaseModel):
    story_prompt: str = Field(..., description="Main comic story concept or plot", alias="story prompt")
    character_name: Optional[str] = Field("Hero", description="Main character name", alias="character name")
    setting: Optional[str] = Field("City", description="Location/Setting (forest, space, city, etc.)")
    tone: Optional[str] = Field("Dramatic", description="Mood/Tone (light-hearted, dramatic, funny, etc.)")
    art_style: Optional[str] = Field("Comic Book", description="Artistic visual style", alias="art style")

    class Config:
        populate_by_name = True

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the homepage input form."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "page_title": "ComicCraft - AI Comic Book Creator"}
    )

@router.post("/generate", response_class=HTMLResponse)
async def generate_comic_form(
    request: Request,
    story_prompt: str = Form(..., alias="story_prompt"),
    character_name: str = Form("Hero", alias="character_name"),
    setting: str = Form("City"),
    tone: str = Form("Dramatic"),
    art_style: str = Form("Comic Book", alias="art_style")
):
    """
    Form submission handler:
    Concatenates user input, runs the AI pipeline (outline -> story -> images -> layout -> PDF),
    and renders comic_preview.html.
    """
    try:
        logger.info(f"Generating comic for prompt: {story_prompt[:60]}...")
        
        # 1. Assemble unified prompt
        full_prompt = (
            f"Story: {story_prompt}. "
            f"Main Character: {character_name}. "
            f"Setting: {setting}. "
            f"Tone: {tone}. "
            f"Art Style: {art_style}."
        )

        # 2. Generate structured 5-panel outline via Gemini Flash
        outline = generate_outline(full_prompt)

        # 3. Generate detailed narration & dialogue via Gemini Pro
        full_story = generate_story(outline)

        # 4. Generate illustrations for each panel via Stable Diffusion
        image_paths = []
        for panel in outline:
            p_prompt = panel.get("image_prompt", "")
            # Ensure art style is baked into the image prompt
            combined_img_prompt = f"{p_prompt}, {art_style} style, comic art, high resolution"
            img_path = generate_image(combined_img_prompt)
            image_paths.append(img_path)

        # 5. Build structured comic layout
        layout = build_comic_layout(image_paths, full_story, outline)

        # 6. Compile into PDF
        pdf_path = save_pdf(layout)

        # Web-accessible PDF path
        web_pdf_path = f"/{pdf_path}" if not pdf_path.startswith("/") else pdf_path

        return templates.TemplateResponse(
            "comic_preview.html",
            {
                "request": request,
                "layout": layout,
                "pdf_path": web_pdf_path,
                "story_prompt": story_prompt,
                "character_name": character_name,
                "setting": setting,
                "tone": tone,
                "art_style": art_style
            }
        )
    except Exception as e:
        logger.error(f"Error during comic generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate comic: {str(e)}")

@router.post("/generate-comic/json")
async def generate_comic_json(payload: PromptRequest):
    """
    JSON API endpoint:
    Processes JSON payload, runs the comic generation pipeline,
    and returns layout data with PDF path.
    """
    try:
        full_prompt = (
            f"Story: {payload.story_prompt}. "
            f"Main Character: {payload.character_name}. "
            f"Setting: {payload.setting}. "
            f"Tone: {payload.tone}. "
            f"Art Style: {payload.art_style}."
        )

        outline = generate_outline(full_prompt)
        full_story = generate_story(outline)

        image_paths = []
        for panel in outline:
            p_prompt = panel.get("image_prompt", "")
            combined_img_prompt = f"{p_prompt}, {payload.art_style} style, comic art"
            img_path = generate_image(combined_img_prompt)
            image_paths.append(img_path)

        layout = build_comic_layout(image_paths, full_story, outline)
        pdf_path = save_pdf(layout)
        web_pdf_path = f"/{pdf_path}" if not pdf_path.startswith("/") else pdf_path

        return JSONResponse({
            "status": "success",
            "pdf_path": web_pdf_path,
            "panels_count": len(layout),
            "layout": layout
        })
    except Exception as e:
        logger.error(f"Error in JSON comic generation: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.get("/export-success", response_class=HTMLResponse)
async def export_success(request: Request, pdf_path: str = Query(...)):
    """Render the export confirmation page with download action."""
    web_pdf_path = f"/{pdf_path}" if not pdf_path.startswith("/") else pdf_path
    return templates.TemplateResponse(
        "export_success.html",
        {
            "request": request,
            "pdf_path": web_pdf_path
        }
    )

@router.get("/download-pdf")
async def download_pdf(pdf_path: str = Query(...)):
    """Directly serve the compiled PDF file as an attachment download."""
    clean_path = pdf_path.lstrip("/")
    if not os.path.exists(clean_path):
        raise HTTPException(status_code=404, detail="Requested PDF file was not found on server.")
    
    filename = os.path.basename(clean_path)
    return FileResponse(
        path=clean_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/test-image")
async def test_image(
    request: Request,
    prompt: str = Query(
        "A brave superhero standing atop a skyscraper under stormy skies, comic book style, bold inks, dynamic lighting"
    )
):
    """
    Developer utility route to test Stable Diffusion / image generation directly.
    """
    try:
        img_path = generate_image(prompt)
        web_path = f"/{img_path}" if not img_path.startswith("/") else img_path

        # Return HTML preview or JSON based on accept header
        if "text/html" in request.headers.get("accept", ""):
            return HTMLResponse(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>ComicCraft - Image Test</title>
                <style>
                    body {{ font-family: system-ui, sans-serif; background: #0f1322; color: #fff; text-align: center; padding: 40px; }}
                    .box {{ max-width: 600px; margin: 0 auto; background: #1a1f36; padding: 24px; border-radius: 16px; border: 2px solid #ffcc00; }}
                    img {{ max-width: 100%; border-radius: 12px; border: 3px solid #000; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
                    a {{ color: #ffcc00; text-decoration: none; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="box">
                    <h2>🎨 Image Generation Test</h2>
                    <p><strong>Prompt:</strong> {prompt}</p>
                    <img src="{web_path}" alt="Generated Image" />
                    <p style="margin-top: 20px;">
                        <a href="/">← Return to ComicCraft</a> | <a href="{web_path}" target="_blank">View Raw Image</a>
                    </p>
                </div>
            </body>
            </html>
            """)
        return JSONResponse({
            "status": "success",
            "prompt": prompt,
            "image_path": web_path
        })
    except Exception as e:
        logger.error(f"Test image generation failed: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
