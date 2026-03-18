"""
answer_extraction_math_service.py
----------------------------------
Service for extracting answers from math test barem PDFs using camelot-py.
Handles multi-row exercises and multi-page spanning with table detection.
"""

import re
from pathlib import Path
from typing import Dict, Optional
import tempfile

import camelot
from pdf2image import convert_from_path
from PIL import Image
from sqlalchemy.orm import Session

from app.models.db_models import AnswerDB, QuestionDB


RENDER_DPI = 200
EXERCISE_NUM_RE = re.compile(r"^(\d{1,2})([a-z])?[\.\)]")


def _get_test_name_from_barem(barem_filename: str) -> str:
    return barem_filename.replace("_barem", "_test")


def _extract_exercise_number(text: str) -> Optional[int]:
    if not text:
        return None
    match = EXERCISE_NUM_RE.match(text.strip())
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _crop_and_save(
    page_image: Image.Image,
    bbox: tuple,
    page_height: float,
    page_width: float,
    output_path: Path
) -> bool:
    """Crop bbox from page image and save."""
    try:
        x1, y1, x2, y2 = bbox
        img_w, img_h = page_image.size
        
        # Scale from PDF points to image pixels
        scale_x = img_w / page_width
        scale_y = img_h / page_height
        
        # Camelot uses bottom-left origin, image uses top-left
        # So we need to flip Y
        x0_px = int(x1 * scale_x)
        x1_px = int(x2 * scale_x)
        y0_px = int((page_height - y2) * scale_y)
        y1_px = int((page_height - y1) * scale_y)
        
        # Clamp to bounds
        x0_px = max(0, min(x0_px, img_w))
        x1_px = max(0, min(x1_px, img_w))
        y0_px = max(0, min(y0_px, img_h))
        y1_px = max(0, min(y1_px, img_h))
        
        if x1_px <= x0_px or y1_px <= y0_px:
            return False
        
        if (x1_px - x0_px) < 20 or (y1_px - y0_px) < 10:
            return False
        
        cropped = page_image.crop((x0_px, y0_px, x1_px, y1_px))
        cropped.save(str(output_path), optimize=True)
        return True
        
    except Exception as e:
        print(f"Crop error: {e}")
        return False


def extract_and_save_answers(
    pdf_content: bytes,
    pdf_filename: str,
    db: Session,
    output_base_dir: Path = Path("exercises"),
    dpi: int = RENDER_DPI
) -> Dict:
    """Extract answers using camelot-py table detection."""
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        tmp_pdf.write(pdf_content)
        tmp_pdf_path = tmp_pdf.name

    try:
        test_filename = _get_test_name_from_barem(pdf_filename)
        pdf_stem = Path(test_filename).stem
        output_dir = output_base_dir / pdf_stem
        output_dir.mkdir(parents=True, exist_ok=True)

        # Render pages to images
        print(f"Rendering PDF pages to images at {dpi} DPI...")
        import sys
        sys.stdout.flush()
        pages_images = convert_from_path(tmp_pdf_path, dpi=dpi)
        print(f"Rendered {len(pages_images)} pages")
        sys.stdout.flush()
        
        # Extract tables using camelot (lattice mode for bordered tables)
        print(f"Extracting tables with camelot...")
        tables = camelot.read_pdf(tmp_pdf_path, pages='all', flavor='lattice')
        
        print(f"Found {tables.n} tables across all pages")
        
        saved_count = 0
        saved_answers = []
        
        # Track column indices across tables (for continuation pages)
        last_answer_col = None
        last_steps_col = None
        
        # Track exercises that span across pages
        pending_exercise = None  # Exercise number that continues to next page
        
        # Collect all exercise data across all tables first
        all_exercises = {}  # ex_num -> {"answer_cells": [], "steps_cells": [], "page": int}
        
        for table_idx, table in enumerate(tables):
            df = table.df  # Get pandas DataFrame
            page_num = table.page
            
            print(f"\n=== Table {table_idx + 1} (Page {page_num}) ===")
            print(f"Shape: {df.shape} (rows x cols)")
            print(f"Columns: {list(df.columns)}")
            
            # Display first few rows for debugging
            try:
                print("First 3 rows:")
                print(df.head(3))
            except UnicodeEncodeError:
                print("First 3 rows: (Unicode display error)")
            
            # Find column indices for answer and steps
            header_row = df.iloc[0]  # First row is usually header
            answer_col = None
            steps_col = None
            
            for col_idx, cell_text in enumerate(header_row):
                cell_lower = str(cell_text).lower()
                if 'răspuns' in cell_lower or 'corect' in cell_lower:
                    answer_col = col_idx
                    print(f"Found answer column: {col_idx}")
                if 'etape' in cell_lower or 'rezolv' in cell_lower:
                    steps_col = col_idx
                    print(f"Found steps column: {col_idx}")
            
            # If no columns found but we have previous columns, check if table structure matches
            if answer_col is None and steps_col is None and (last_answer_col is not None or last_steps_col is not None):
                # This might be a continuation page - check if column count matches
                if last_answer_col is not None and last_answer_col < len(header_row):
                    answer_col = last_answer_col
                    print(f"Using previous answer column: {answer_col} (continuation page)")
                if last_steps_col is not None and last_steps_col < len(header_row):
                    steps_col = last_steps_col
                    print(f"Using previous steps column: {steps_col} (continuation page)")
            
            if answer_col is None and steps_col is None:
                print("Could not identify answer/steps columns")
                continue
            
            # Save column indices for next table (continuation pages)
            if answer_col is not None:
                last_answer_col = answer_col
            if steps_col is not None:
                last_steps_col = steps_col
            
            # Get page dimensions from camelot
            page_width, page_height = table.pdf_size if hasattr(table, 'pdf_size') else (595.32, 841.92)
            
            # Get page image
            page_image = pages_images[page_num - 1]  # 0-indexed
            
            # Group rows by exercise (handle multi-row exercises)
            exercise_rows = {}  # ex_num -> list of row indices
            current_ex = None
            
            # If there's a pending exercise from previous page, start with it
            if pending_exercise is not None:
                current_ex = pending_exercise
                exercise_rows[current_ex] = []
                print(f"  Continuing exercise {current_ex} from previous page")
            
            # For continuation pages, start from row 0 (no header row)
            # For first page, skip row 0 (it has headers)
            start_row = 0 if (answer_col == last_answer_col and steps_col == last_steps_col and table_idx > 0) else 1
            
            # Process data rows
            for row_idx in range(start_row, len(df)):
                row = df.iloc[row_idx]
                
                # Get exercise number from first cell
                first_cell = str(row.iloc[0]).strip()
                ex_num = _extract_exercise_number(first_cell)
                
                if ex_num is not None:
                    # Start of new exercise
                    current_ex = ex_num
                    if ex_num not in exercise_rows:
                        exercise_rows[ex_num] = []
                    exercise_rows[ex_num].append(row_idx)
                elif current_ex is not None:
                    # Continuation row for current exercise
                    exercise_rows[current_ex].append(row_idx)
            
            # Check if last exercise might continue on next page
            # (if last rows belong to current_ex and we're not on the last table)
            if current_ex is not None and table_idx < len(tables) - 1:
                pending_exercise = current_ex
            else:
                pending_exercise = None
            
            print(f"  Found exercises: {list(exercise_rows.keys())}")
            
            # Collect cells for each exercise in this table
            for ex_num, row_indices in exercise_rows.items():
                # Initialize exercise data if not exists
                if ex_num not in all_exercises:
                    all_exercises[ex_num] = {
                        "answer_cells": [],
                        "steps_cells": [],
                        "page": page_num
                    }
                
                # Collect answer cells
                if answer_col is not None:
                    for row_idx in row_indices:
                        if row_idx < len(table.cells) and answer_col < len(table.cells[row_idx]):
                            cell = table.cells[row_idx][answer_col]
                            all_exercises[ex_num]["answer_cells"].append((cell, page_num, page_width, page_height))
                
                # Collect steps cells
                if steps_col is not None:
                    for row_idx in row_indices:
                        if row_idx < len(table.cells) and steps_col < len(table.cells[row_idx]):
                            cell = table.cells[row_idx][steps_col]
                            all_exercises[ex_num]["steps_cells"].append((cell, page_num, page_width, page_height))
        
        # Now process all collected exercises
        print(f"\nProcessing {len(all_exercises)} exercises...")
        
        for ex_num in sorted(all_exercises.keys()):
            data = all_exercises[ex_num]
            print(f"  Exercise {ex_num} (page {data['page']})")
            
            answer_saved = False
            steps_saved = False
            
            # Process answer cells
            if data["answer_cells"]:
                # Group cells by page
                cells_by_page = {}
                for cell, page_num, pw, ph in data["answer_cells"]:
                    if page_num not in cells_by_page:
                        cells_by_page[page_num] = {"cells": [], "pw": pw, "ph": ph}
                    cells_by_page[page_num]["cells"].append(cell)
                
                # Crop from each page and stitch vertically if multi-page
                page_crops = []
                for page_num in sorted(cells_by_page.keys()):
                    cells = cells_by_page[page_num]["cells"]
                    pw = cells_by_page[page_num]["pw"]
                    ph = cells_by_page[page_num]["ph"]
                    
                    # Merge cells on this page
                    x1 = min(c.x1 for c in cells)
                    y1 = min(c.y1 for c in cells)
                    x2 = max(c.x2 for c in cells)
                    y2 = max(c.y2 for c in cells)
                    bbox = (x1, y1, x2, y2)
                    
                    # Crop from page
                    page_image = pages_images[page_num - 1]
                    img_w, img_h = page_image.size
                    scale_x = img_w / pw
                    scale_y = img_h / ph
                    
                    x0_px = int(x1 * scale_x)
                    x1_px = int(x2 * scale_x)
                    y0_px = int((ph - y2) * scale_y)
                    y1_px = int((ph - y1) * scale_y)
                    
                    x0_px = max(0, min(x0_px, img_w))
                    x1_px = max(0, min(x1_px, img_w))
                    y0_px = max(0, min(y0_px, img_h))
                    y1_px = max(0, min(y1_px, img_h))
                    
                    if x1_px > x0_px and y1_px > y0_px and (x1_px - x0_px) >= 20 and (y1_px - y0_px) >= 10:
                        cropped = page_image.crop((x0_px, y0_px, x1_px, y1_px))
                        page_crops.append(cropped)
                
                # Stitch pages vertically if needed
                if page_crops:
                    if len(page_crops) == 1:
                        final_image = page_crops[0]
                    else:
                        # Stitch vertically
                        total_height = sum(img.height for img in page_crops)
                        max_width = max(img.width for img in page_crops)
                        final_image = Image.new('RGB', (max_width, total_height), 'white')
                        y_offset = 0
                        for crop in page_crops:
                            final_image.paste(crop, (0, y_offset))
                            y_offset += crop.height
                    
                    answer_path = output_dir / f"exercise_{ex_num:02d}_answer.png"
                    final_image.save(str(answer_path), optimize=True)
                    answer_saved = True
                    print(f"    Answer: True ({sum(len(cells_by_page[p]['cells']) for p in cells_by_page)} cells across {len(cells_by_page)} pages)")
            
            # Process steps cells (same logic)
            if data["steps_cells"]:
                cells_by_page = {}
                for cell, page_num, pw, ph in data["steps_cells"]:
                    if page_num not in cells_by_page:
                        cells_by_page[page_num] = {"cells": [], "pw": pw, "ph": ph}
                    cells_by_page[page_num]["cells"].append(cell)
                
                page_crops = []
                for page_num in sorted(cells_by_page.keys()):
                    cells = cells_by_page[page_num]["cells"]
                    pw = cells_by_page[page_num]["pw"]
                    ph = cells_by_page[page_num]["ph"]
                    
                    x1 = min(c.x1 for c in cells)
                    y1 = min(c.y1 for c in cells)
                    x2 = max(c.x2 for c in cells)
                    y2 = max(c.y2 for c in cells)
                    bbox = (x1, y1, x2, y2)
                    
                    page_image = pages_images[page_num - 1]
                    img_w, img_h = page_image.size
                    scale_x = img_w / pw
                    scale_y = img_h / ph
                    
                    x0_px = int(x1 * scale_x)
                    x1_px = int(x2 * scale_x)
                    y0_px = int((ph - y2) * scale_y)
                    y1_px = int((ph - y1) * scale_y)
                    
                    x0_px = max(0, min(x0_px, img_w))
                    x1_px = max(0, min(x1_px, img_w))
                    y0_px = max(0, min(y0_px, img_h))
                    y1_px = max(0, min(y1_px, img_h))
                    
                    if x1_px > x0_px and y1_px > y0_px and (x1_px - x0_px) >= 20 and (y1_px - y0_px) >= 10:
                        cropped = page_image.crop((x0_px, y0_px, x1_px, y1_px))
                        page_crops.append(cropped)
                
                if page_crops:
                    if len(page_crops) == 1:
                        final_image = page_crops[0]
                    else:
                        total_height = sum(img.height for img in page_crops)
                        max_width = max(img.width for img in page_crops)
                        final_image = Image.new('RGB', (max_width, total_height), 'white')
                        y_offset = 0
                        for crop in page_crops:
                            final_image.paste(crop, (0, y_offset))
                            y_offset += crop.height
                    
                    steps_path = output_dir / f"exercise_{ex_num:02d}_steps.png"
                    final_image.save(str(steps_path), optimize=True)
                    steps_saved = True
                    print(f"    Steps: True ({sum(len(cells_by_page[p]['cells']) for p in cells_by_page)} cells across {len(cells_by_page)} pages)")
                
                if not (answer_saved or steps_saved):
                    continue
                
                print(f"    Saving to database...")
                
                # Save to database
                answer_rel_path = None
                steps_rel_path = None
                
                if answer_saved:
                    answer_rel_path = f"{output_dir.relative_to(output_base_dir.parent)}/exercise_{ex_num:02d}_answer.png".replace("\\", "/")
                if steps_saved:
                    steps_rel_path = f"{output_dir.relative_to(output_base_dir.parent)}/exercise_{ex_num:02d}_steps.png".replace("\\", "/")
                
                primary_path = answer_rel_path if answer_rel_path else steps_rel_path
                
                # Find the question for this exercise from THIS specific test
                # Match by question_number AND path containing the test directory
                question = db.query(QuestionDB).filter(
                    QuestionDB.question_number == ex_num,
                    QuestionDB.path_to_question.like(f"%{pdf_stem}%")
                ).first()
                
                if question:
                    # Check if this question already has an answer
                    if question.answer_id:
                        # Update existing answer
                        existing_answer = db.query(AnswerDB).filter(AnswerDB.id == question.answer_id).first()
                        if existing_answer:
                            existing_answer.path_to_answer = primary_path
                            existing_answer.question_number = ex_num
                            answer_id = existing_answer.id
                            print(f"    Updated existing answer (id={answer_id})")
                        else:
                            # Answer ID exists but answer not found, create new
                            answer = AnswerDB(path_to_answer=primary_path, question_number=ex_num)
                            db.add(answer)
                            db.flush()
                            answer_id = answer.id
                            question.answer_id = answer_id
                            print(f"    Created new answer (id={answer_id})")
                    else:
                        # Create new answer for this question
                        answer = AnswerDB(path_to_answer=primary_path, question_number=ex_num)
                        db.add(answer)
                        db.flush()
                        answer_id = answer.id
                        question.answer_id = answer_id
                        print(f"    Created new answer and linked to question (id={answer_id})")
                else:
                    # No matching question found - create orphan answer
                    answer = AnswerDB(path_to_answer=primary_path, question_number=ex_num)
                    db.add(answer)
                    db.flush()
                    answer_id = answer.id
                    print(f"    Warning: No question found for exercise {ex_num} in {pdf_stem}, created orphan answer (id={answer_id})")
                
                saved_count += 1
                saved_answers.append({
                    "exercise_number": ex_num,
                    "answer_path": answer_rel_path,
                    "steps_path": steps_rel_path,
                    "page": page_num
                })
                
                print(f"    Total saved so far: {saved_count}")

        db.commit()

        return {
            "success": True,
            "message": f"Successfully extracted {saved_count} answers using camelot-py",
            "answers_saved": saved_count,
            "answers": saved_answers,
            "output_directory": str(output_dir),
            "linked_to_test": test_filename
        }

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "answers_saved": 0
        }
    finally:
        Path(tmp_pdf_path).unlink(missing_ok=True)
