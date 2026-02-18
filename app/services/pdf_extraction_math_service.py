"""
pdf_extraction_service.py
--------------------------
Service for extracting exercises from structured math test PDFs.
Handles exercises with sub-points and multi-page continuations.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional
import tempfile

import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
from sqlalchemy.orm import Session

from app.models.db_models import QuestionDB
from app.models.question import QuestionType


# ─── Configuration ────────────────────────────────────────────────────────────

RENDER_DPI = 200
LEFT_MARGIN_FRACTION = 0.20
PADDING_TOP = 8
PADDING_BOTTOM = 8
STITCH_BG = (255, 255, 255)
STITCH_SEP_PX = 2
STITCH_SEP_COLOR = (200, 200, 200)

EXERCISE_NUM_RE = re.compile(r"^(\d{1,2})\.$")
SUBPOINT_RE = re.compile(r"^[a-z]\)$")
LANGUAGE_RE = re.compile(r"(?:^|[_\-\.\s])(ro|ru|en)(?:[_\-\.\s]|$)", re.IGNORECASE)


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _new_exercise(number: int, page_idx: int, y_top: float,
                  page_h: float, page_w: float) -> dict:
    return {
        "number": number,
        "spans": [
            {
                "page": page_idx,
                "y_top": y_top,
                "y_bottom": page_h,
                "page_height": page_h,
                "page_width": page_w,
            }
        ],
    }


def _current_span(ex: dict) -> dict:
    return ex["spans"][-1]


def _extend_to_page(ex: dict, page_idx: int, page_h: float, page_w: float) -> None:
    ex["spans"].append(
        {
            "page": page_idx,
            "y_top": 0.0,
            "y_bottom": page_h,
            "page_height": page_h,
            "page_width": page_w,
        }
    )


def _pt_to_px(pt: float, page_h_pt: float, img_h_px: int) -> int:
    return int(pt * img_h_px / page_h_pt)


def extract_language_from_filename(filename: str) -> Optional[str]:
    """
    Extract language code from PDF filename.
    Looks for 'ro', 'ru', or 'en' as a standalone token separated by
    underscores, hyphens, dots, spaces, or at the start/end of the stem.
    Returns the lowercase language code, or None if not found.
    """
    stem = Path(filename).stem
    match = LANGUAGE_RE.search(stem)
    if match:
        return match.group(1).lower()
    return None


# ─── Core Extraction Functions ────────────────────────────────────────────────

def find_exercise_boundaries(pdf_path: str) -> List[dict]:
    """
    Scan every page and return a list of exercise dicts.
    """
    exercises: List[dict] = []
    open_ex: Optional[dict] = None
    last_num: int = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_h = page.height
            page_w = page.width
            left_limit = page_w * LEFT_MARGIN_FRACTION

            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=False,
            )

            if open_ex is not None:
                last_span = _current_span(open_ex)
                if last_span["page"] < page_idx:
                    _extend_to_page(open_ex, page_idx, page_h, page_w)

            for word in words:
                text = word["text"].strip()
                y = word["top"]
                x = word["x0"]

                m = EXERCISE_NUM_RE.match(text)
                if m and x < left_limit:
                    num = int(m.group(1))

                    if num == last_num + 1:
                        if open_ex is not None:
                            span = _current_span(open_ex)
                            if span["page"] == page_idx:
                                span["y_bottom"] = y
                            exercises.append(open_ex)

                        open_ex = _new_exercise(num, page_idx, y, page_h, page_w)
                        last_num = num

            if open_ex is not None:
                span = _current_span(open_ex)
                if span["page"] == page_idx:
                    span["y_bottom"] = max(span["y_bottom"], page_h)

    if open_ex is not None:
        exercises.append(open_ex)

    return exercises


def render_exercise(exercise: dict, pages_images: List[Image.Image]) -> Optional[Image.Image]:
    """
    Build a single PIL Image for the exercise by cropping and stitching.
    """
    slices: List[Image.Image] = []

    for span in exercise["spans"]:
        page_img = pages_images[span["page"]]
        img_w, img_h = page_img.size
        page_h_pt = span["page_height"]

        y_top_pt = max(0.0, span["y_top"] - PADDING_TOP)
        y_bot_pt = min(page_h_pt, span["y_bottom"] + PADDING_BOTTOM)

        y_top_px = max(0, _pt_to_px(y_top_pt, page_h_pt, img_h))
        y_bot_px = min(img_h, _pt_to_px(y_bot_pt, page_h_pt, img_h))

        if y_bot_px - y_top_px < 4:
            continue

        slices.append(page_img.crop((0, y_top_px, img_w, y_bot_px)))

    if not slices:
        return None
    if len(slices) == 1:
        return slices[0]

    total_w = max(s.width for s in slices)
    sep_h = STITCH_SEP_PX
    total_h = sum(s.height for s in slices) + sep_h * (len(slices) - 1)

    canvas = Image.new("RGB", (total_w, total_h), STITCH_BG)
    y_cursor = 0

    for i, sl in enumerate(slices):
        canvas.paste(sl, (0, y_cursor))
        y_cursor += sl.height

        if i < len(slices) - 1 and sep_h > 0:
            sep_strip = Image.new("RGB", (total_w, sep_h), STITCH_SEP_COLOR)
            canvas.paste(sep_strip, (0, y_cursor))
            y_cursor += sep_h

    return canvas


# ─── Main Service Function ────────────────────────────────────────────────────

def extract_and_save_questions(
    pdf_content: bytes,
    pdf_filename: str,
    db: Session,
    output_base_dir: Path = Path("exercises"),
    question_type: QuestionType = QuestionType.MATH,
    dpi: int = RENDER_DPI
) -> Dict[str, any]:
    """
    Extract questions from PDF and save to database.
    
    Args:
        pdf_content: PDF file content as bytes
        pdf_filename: Original filename
        db: Database session
        output_base_dir: Base directory for saving extracted images
        question_type: Type of questions (default: MATH)
        dpi: Resolution for rendering
    
    Returns:
        Dict with extraction results
    """
    # Detect language from filename
    language = extract_language_from_filename(pdf_filename)

    # Create temporary PDF file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        tmp_pdf.write(pdf_content)
        tmp_pdf_path = tmp_pdf.name

    try:
        # Create output directory
        pdf_stem = Path(pdf_filename).stem
        output_dir = output_base_dir / pdf_stem
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find exercise boundaries
        exercises = find_exercise_boundaries(tmp_pdf_path)
        
        if not exercises:
            return {
                "success": False,
                "message": "No exercises detected in PDF",
                "questions_saved": 0
            }

        # Render PDF pages
        pages_images = convert_from_path(tmp_pdf_path, dpi=dpi)

        # Extract and save each exercise
        saved_count = 0
        saved_questions = []

        for ex in exercises:
            img = render_exercise(ex, pages_images)
            if img is None:
                continue

            # Save image
            img_filename = f"exercise_{ex['number']:02d}.png"
            img_path = output_dir / img_filename
            img.save(str(img_path), optimize=True)

            # Create relative path for database storage
            relative_path = f"{output_dir.relative_to(output_base_dir.parent)}/{img_filename}".replace("\\", "/")

            # Save to database
            question = QuestionDB(
                path_to_question=relative_path,
                answer_id=None,  # No answer yet - can be updated later
                type=question_type,
                question_number=ex['number'],
                language=language
            )
            db.add(question)
            saved_count += 1
            saved_questions.append({
                "number": ex['number'],
                "path": relative_path
            })

        db.commit()

        return {
            "success": True,
            "message": f"Successfully extracted and saved {saved_count} questions",
            "questions_saved": saved_count,
            "questions": saved_questions,
            "output_directory": str(output_dir)
        }

    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "message": f"Error during extraction: {str(e)}",
            "questions_saved": 0
        }
    finally:
        # Clean up temporary PDF
        Path(tmp_pdf_path).unlink(missing_ok=True)
