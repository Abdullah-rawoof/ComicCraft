import os
import logging
from datetime import datetime
from pathlib import Path
from fpdf import FPDF

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("static/exports")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

class ComicPDF(FPDF):
    """Custom Comic PDF generator with headers and styling."""
    def header(self):
        # We handle custom headers per page in save_pdf
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(140, 140, 150)
        self.cell(0, 10, f"ComicCraft - AI Comic Book Creator | Page {self.page_no()}", align="C")

def save_pdf(layout: list[dict]) -> str:
    """
    Compile comic layout (images, titles, narration, dialogue) into a multi-page PDF using FPDF.
    Uses Unicode DejaVu fonts and saves to static/exports/ with a timestamp.
    Returns the file path to the saved PDF.
    """
    logger.info("Compiling comic into PDF...")
    pdf = ComicPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)

    # Register DejaVu fonts
    font_regular = "static/fonts/DejaVuSans.ttf"
    font_bold = "static/fonts/DejaVuSans-Bold.ttf"
    font_italic = "static/fonts/DejaVuSans-Oblique.ttf"

    font_family = "Helvetica"
    has_dejavu = False

    if os.path.exists(font_regular):
        try:
            pdf.add_font("DejaVu", "", font_regular)
            if os.path.exists(font_bold):
                pdf.add_font("DejaVu", "B", font_bold)
            else:
                pdf.add_font("DejaVu", "B", font_regular)

            if os.path.exists(font_italic):
                pdf.add_font("DejaVu", "I", font_italic)
            else:
                pdf.add_font("DejaVu", "I", font_regular)
            
            font_family = "DejaVu"
            has_dejavu = True
        except Exception as e:
            logger.warning(f"Could not load DejaVu font in FPDF: {e}. Using Helvetica.")

    # Page width: 210mm, margin 15mm => printable width: 180mm
    content_width = 180

    for idx, panel in enumerate(layout):
        pdf.add_page()

        # Decorative Top Banner
        pdf.set_fill_color(30, 34, 52)
        pdf.rect(0, 0, 210, 20, "F")

        # Top Banner Title
        pdf.set_font(font_family, "B", 11)
        pdf.set_text_color(255, 215, 0)
        pdf.set_xy(15, 6)
        pdf.cell(180, 8, "COMICCRAFT", align="L")
        
        pdf.set_font(font_family, "", 9)
        pdf.set_text_color(200, 210, 230)
        pdf.set_xy(15, 6)
        pdf.cell(180, 8, f"PANEL {panel.get('panel', idx + 1)} OF {len(layout)}", align="R")

        pdf.set_y(26)

        # Panel Title Box
        title = panel.get("title", f"Panel {idx + 1}")
        pdf.set_fill_color(245, 247, 252)
        pdf.set_draw_color(210, 215, 230)
        pdf.rect(15, pdf.get_y(), content_width, 10, "DF")

        pdf.set_font(font_family, "B", 13)
        pdf.set_text_color(20, 25, 40)
        pdf.set_x(18)
        pdf.cell(content_width - 6, 10, title, align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # Panel Image
        # Check local path first, then strip leading slash
        img_path = panel.get("local_image_path") or panel.get("image_path", "")
        if img_path.startswith("/"):
            img_path = img_path[1:]

        if img_path and os.path.exists(img_path):
            try:
                # Max image height 110mm, width 140mm centered
                img_width = 135
                x_pos = (210 - img_width) / 2
                y_pos = pdf.get_y()
                
                # Outer comic image border
                pdf.set_draw_color(30, 35, 55)
                pdf.set_line_width(0.8)
                pdf.rect(x_pos - 1.5, y_pos - 1.5, img_width + 3, img_width + 3)
                
                pdf.image(img_path, x=x_pos, y=y_pos, w=img_width, h=img_width)
                pdf.set_y(y_pos + img_width + 6)
            except Exception as img_err:
                logger.error(f"Error rendering image in PDF: {img_err}")
                pdf.ln(5)
        else:
            pdf.ln(10)

        # Scene Description (Italics callout)
        scene_desc = panel.get("scene_description", "")
        if scene_desc:
            pdf.set_fill_color(255, 252, 235)
            pdf.set_draw_color(245, 210, 110)
            y_start = pdf.get_y()
            pdf.set_font(font_family, "I", 9)
            pdf.set_text_color(80, 70, 40)
            pdf.set_x(18)
            pdf.multi_cell(content_width - 6, 5, f"Scene: {scene_desc}", border=0, align="L")
            pdf.ln(2)

        # Narration & Dialogue
        narration = panel.get("narration", "")
        dialogue = panel.get("dialogue", "")

        if narration:
            pdf.set_font(font_family, "", 10)
            pdf.set_text_color(30, 35, 50)
            pdf.set_x(18)
            pdf.multi_cell(content_width - 6, 5.5, narration, align="L")
            pdf.ln(2)

        if dialogue:
            pdf.set_font(font_family, "B", 10)
            pdf.set_text_color(180, 40, 40)
            pdf.set_x(22)
            pdf.multi_cell(content_width - 14, 5.5, dialogue, align="L")

    # Timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"comic_{timestamp}.pdf"
    output_path = os.path.join("static", "exports", pdf_filename).replace("\\", "/")
    
    pdf.output(output_path)
    logger.info(f"Comic PDF exported successfully to: {output_path}")
    return output_path
