import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routes import router

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("comiccraft")

app = FastAPI(
    title="ComicCraft",
    description="AI Comic Story & Illustration Creator using Google Gemini and Stable Diffusion",
    version="1.0.0"
)

# Enable CORS for open interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directories exist
for folder in ["static", "static/panels", "static/exports", "static/fonts", "static/css", "static/images"]:
    Path(folder).mkdir(parents=True, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include application routes
app.include_router(router)

@app.on_event("startup")
async def startup_event():
    logger.info("==========================================")
    logger.info("   ⚡ ComicCraft Server Starting ⚡")
    logger.info("   FastAPI + Gemini + Stable Diffusion")
    logger.info("==========================================")
