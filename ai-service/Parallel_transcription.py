import os
import subprocess
import logging
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from PIL import Image
from pdf2image import convert_from_path
from google.genai import errors as genai_errors
from tqdm import tqdm
from google.genai import types
from concurrent.futures import ThreadPoolExecutor, as_completed

# 1. Setup Logging
logging.basicConfig(
    filename='transcription.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

def log_and_print(message, is_error=False):
    """Logs to the file and safely prints to the terminal above the tqdm bar."""
    if is_error:
        logging.error(message)
    else:
        logging.info(message)
    tqdm.write(message)

# 2. Setup Gemini
load_dotenv()
# Remplacez par vos vraies informations
PROJECT_ID = "gen-lang-client-0125580043"  # L'ID que vous avez trouvé dans la console
LOCATION = "global"                # Ou votre région préférée

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION
)

STATEMENT_EXTRACTION_MODEL = 'gemini-3-flash-preview'
TRANSCRIPTION_MODEL = 'gemini-3-flash-preview'
LATEX_MODEL = 'gemini-3.1-flash-lite-preview'


def extract_statement_text(pdf_path):
    """Reads PDF locally and sends bytes to Gemini for context extraction."""
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    # Wrap bytes for Vertex AI
    pdf_part = types.Part.from_bytes(
        data=pdf_bytes,
        mime_type="application/pdf"
    )
    
    prompt = "Transcribe the full text of this exam statement PDF accurately. I will use this as context for future OCR tasks."
    
    response = client.models.generate_content(
        model=STATEMENT_EXTRACTION_MODEL,
        contents=[pdf_part, prompt]
    )
    return response.text.strip()




def pdf_to_images(pdf_path, output_folder="extracted_images"):
    os.makedirs(output_folder, exist_ok=True)
    log_and_print("  Converting PDF to images...")
    pages = convert_from_path(pdf_path, dpi=200)

    page_images = []
    for i, page in enumerate(pages):
        page_path = os.path.join(output_folder, f"page_{i+1:02d}.jpg")
        page.save(page_path, "JPEG")
        page_images.append(page_path)
        log_and_print(f"    Saved page {i+1} -> {page_path}")

    return page_images

def split_page(image_path, output_folder, page_num):
    with Image.open(image_path) as img:
        width, height = img.size
        midpoint = width // 2

        left = img.crop((0, 0, midpoint, height))
        right = img.crop((midpoint, 0, width, height))

        left_path = os.path.join(output_folder, f"page_{page_num:02d}_left.jpg")
        right_path = os.path.join(output_folder, f"page_{page_num:02d}_right.jpg")

        left.save(left_path, "JPEG")
        right.save(right_path, "JPEG")

    return left_path, right_path

def build_transcription_order(page_image_paths, output_folder):
    num_pages = len(page_image_paths)
    if num_pages not in (2, 4, 6):
        log_and_print(f"  Warning: expected 2, 4, or 6 pages but got {num_pages}. Proceeding anyway.")

    ordered_images = []
    is_first = True

    for start in range(0, num_pages, 2):
        page1_path = page_image_paths[start]
        page2_path = page_image_paths[start + 1] if (start + 1) < num_pages else None

        left1, right1 = split_page(page1_path, output_folder, start + 1)
        if page2_path:
            left2, right2 = split_page(page2_path, output_folder, start + 2)
        else:
            left2, right2 = None, None

        for img_path in [right1, left2, right2, left1]:
            if img_path is None:
                continue

            if is_first:
                cropped_path = os.path.join(output_folder, "page_01_right_cropped.jpg")
                with Image.open(img_path) as img:
                    width, height = img.size
                    crop_top = int(height * 0.45)
                    cropped = img.crop((0, crop_top, width, height))
                    cropped.save(cropped_path, "JPEG")
                log_and_print(f"    Cropped top 45% from first image -> {cropped_path}")
                ordered_images.append(cropped_path)
                is_first = False
            else:
                ordered_images.append(img_path)

    log_and_print(f"  Final transcription order ({len(ordered_images)} images):")
    for i, p in enumerate(ordered_images, 1):
        log_and_print(f"    {i}. {os.path.basename(p)}")

    return ordered_images

def get_transcription(image_path, extracted_statement_text):
    # On ouvre l'image localement pour lire les octets
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # On crée un dictionnaire pour l'image compatible avec Vertex AI
    student_image = types.Part.from_bytes(
        data=image_bytes,
        mime_type="image/jpeg"
    )

    prompt = f"""
    REFERENCE EXAM STATEMENT (CONTEXT):
    {extracted_statement_text}

    TASK: Transcribe the handwritten French text exactly as written, including any spelling or grammatical mistakes made by the student.

    INTELLIGENT CONTEXT CLUES & MATHEMATICAL COHERENCE:
    - IDENTIFICATION: Actively scan the REFERENCE EXAM STATEMENT for key numerical values, constants, and data points associated with the specific exercise the student is answering.
    - AMBIGUITY RESOLUTION: If a handwritten character is visually unclear or multi-interpretable (e.g., a '3' that looks like a '8'), compare it against the values provided in the corresponding section of the REFERENCE EXAM STATEMENT. Favor the reference value if it is a 70%+ visual match.
    - COMPUTATIONAL VALIDATION: Check the student's arithmetic. If the student performs a calculation (e.g., a fraction or sum) and the result is mathematically consistent with a value from the statement but inconsistent with a literal OCR reading, transcribe the value that makes the math correct. 
    - EXAMPLE LOGIC: If a student writes "x * (x + y + z) = 0.7", and 'x' looks like '0.82' but the statement provides '0.32', use '0.32' because the calculation is only valid with that reference value.
    - LIMIT: Do not "fix" clear student errors where the math is simply wrong; only use this logic to resolve visual uncertainty between the handwriting and the provided context.

    EMPTY PAGE HANDLING (CRITICAL):
    - If the image contains NO student handwriting (e.g., it is a completely blank page, or only contains printed template lines without answers), output exactly the word "NULL" and nothing else.
    
    FLAT TEXT STRATEGY:
    - Ignore visual indentation/layout from the image.
    - Start every new point (1, 2, a, b, etc.) on a fresh line at the left margin.
    - Do not use leading spaces or tabs to represent indentation.
    
    MATH & SPECIAL CHARACTERS:
    - Use $...$ for inline math and $$...$$ for standalone equations.
    - Ensure special LaTeX characters in regular text (like & or %) are escaped (e.g., \\&, \\%).
    
    FILTERS:
    - Ignore any box containing "nom, prénom et signature de l'enseignant correcteur".
    - Ignore any short page codes/barcodes at the top (e.g., "V1 666F").
    - Categorize deletions:
        1. LEGIBLE DELETIONS: Wrap in double tildes: ~~texte annulé~~.
        2. ILLEGIBLE DELETIONS: Use the tag [Rature illisible].
    
    NON-TEXT ELEMENTS:
    - If the image contains a diagram or figure, describe it IN FRENCH in words within bold brackets. 
      Example: **[Description: Un diagramme montrant une courbe de distribution]**.
    """
    # Build the contents list dynamically
    contents = []
    contents.append(student_image)
    contents.append(prompt)

    response = client.models.generate_content(
        model=TRANSCRIPTION_MODEL,
        contents=contents
    )
            
    return response.text.strip()

def build_latex_document(raw_text):
    prompt = f"""
    You are a LaTeX expert. Convert the following raw transcription of a French student exam into a complete, compilable LaTeX document.


    DOCUMENT STRUCTURE:
    - Use \\documentclass{{article}}
    - Use packages: amsmath, amssymb, geometry (margin=2.5cm), enumitem.
    - CRITICAL: We are using XeLaTeX. DO NOT use inputenc or fontenc.
    - Add these EXACT lines to the preamble for Arabic support:
      \\usepackage{{fontspec}}
      \\usepackage{{polyglossia}}
      \\setmainlanguage{{french}}
      \\setotherlanguage{{arabic}}
      \\newfontfamily\\arabicfont[Script=Arabic]{{Arial}}
    - Add \\usepackage[normalem]{{ulem}} to the preamble.
    - CRITICAL TITLE RULES: DO NOT use \\title{{}}, \\maketitle, \\begin{{titlepage}}, or \\newpage. 
    - Instead, just put \\begin{{center}}\\Large\\textbf{{Transcription de l'examen}}\\end{{center}} at the very beginning of the document body.
    - Detect exercise headings (e.g., "Exercice 1") and use \\section*{{...}}.

    FORMATTING RULES:
    - HANDLING LEGIBLE DELETIONS: The raw text may contain deleted text wrapped in double tildes (e.g., ~~deleted text~~). Convert these into the \\sout{{...}} command from the ulem package. Example: \\sout{{deleted text}}.
    - HANDLING ILLEGIBLE DELETIONS: The raw text may contain the exact tag [Rature illisible]. You MUST completely remove and ignore this tag. It should NOT be printed or included in the final LaTeX document.
    - If the student wrote any Arabic text, you MUST wrap it in \\textarabic{{...}}. Example: \\textarabic{{مرحبا}}
    - Keep all student mistakes exactly as written.
    - Use $...$ for inline math and \\[ ... \\] for display math.
    - Any bold text descriptions of diagrams (e.g., **[Description: ...]**) must be wrapped in \\textbf{{...}}.
    - Ensure a blank line or \\vspace{{0.5em}} between main questions for readability.
    
    - LISTS & ENUMERATION (CRITICAL):
    - DO NOT rely on LaTeX's automatic numbering (standard \\item). Students often skip questions, restart numbering, or use inconsistent formats.
    - You MUST explicitly define the label for EVERY item in a list to exactly match the student's handwriting, using the syntax \\item[<student_label>].
    - Examples: If the student wrote "3)", use \\item[3)]. If they wrote "2.", use \\item[2.]. If they wrote "a)", use \\item[a)].
    - Use \\begin{{itemize}} ... \\end{{itemize}} for all lists and nested lists to prevent any auto-incrementing conflicts, and just force the labels manually with \\item[...].

    CRITICAL OUTPUT FORMAT:
    - Return ONLY the raw LaTeX code. 
    - DO NOT include any conversational filler, explanations, or greetings (e.g., "Voici la transcription...").
    - DO NOT wrap the output in markdown code blocks (do NOT use ```latex ... ```).
    - The very first characters of your response MUST be \\documentclass{{article}}.

    RAW TRANSCRIPTION:
    {raw_text}
    """

    response = client.models.generate_content(
        model=LATEX_MODEL,
        contents=[prompt]
    )
    return response.text

def save_to_pdf(latex_content, output_filename):
    tex_path = output_filename + ".tex"
    pdf_path = output_filename + ".pdf" 

    latex_content = latex_content.strip()
    if latex_content.startswith("```"):
        latex_content = "\n".join(latex_content.split("\n")[1:])
    if latex_content.endswith("```"):
        latex_content = "\n".join(latex_content.split("\n")[:-1])

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex_content)
    log_and_print(f"  .tex file saved as {tex_path}")

    log_and_print(f"  Compiling {tex_path} with xelatex...")
    try:
        # Changed pdflatex to xelatex here
        result = subprocess.run(
            ["xelatex", "-output-directory", os.path.dirname(tex_path), "--interaction=nonstopmode", tex_path],
            capture_output=True
        )
        
        # Check if the PDF file actually exists now
        if os.path.exists(pdf_path):
            if result.returncode != 0:
                log_and_print("  ⚠️ xelatex had minor warnings, but the PDF was generated successfully!")
            else:
                log_and_print(f"  ✅ PDF compiled successfully!")
        else:
            log_and_print("  ❌ xelatex completely failed to generate the PDF:", is_error=True)
            log_and_print("\n".join(result.stdout.decode("utf-8", errors="replace").splitlines()[-15:]), is_error=True)
            
    except FileNotFoundError:
        log_and_print("  xelatex not found. Make sure your LaTeX distribution is up to date.", is_error=True)


# --- Single-File Processing (for API use) ---
def transcribe_single_pdf(pdf_path, statement_text="", temp_dir=None):
    """
    Transcribes a single handwritten exam PDF and returns the raw text.
    This is the API-friendly version — no LaTeX/PDF generation.
    
    Args:
        pdf_path: Path to the student's handwritten exam PDF.
        statement_text: Optional extracted exam statement text for context.
        temp_dir: Optional temp directory for intermediate images.
        
    Returns:
        str: The full raw transcription text.
    """
    import tempfile
    
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="sallahli_ocr_")
    
    os.makedirs(temp_dir, exist_ok=True)
    
    log_and_print(f"📄 Transcribing single PDF: {os.path.basename(pdf_path)}")
    log_and_print(f"[MODEL] transcription: {TRANSCRIPTION_MODEL}")
    
    # Step 1: Convert PDF to images
    page_paths = pdf_to_images(pdf_path, output_folder=temp_dir)
    
    # Step 2: Build the correct reading order
    ordered_images = build_transcription_order(page_paths, output_folder=temp_dir)
    
    # Step 3: Transcribe each image
    log_and_print("  Starting transcription...")
    full_text = ""
    consecutive_blank_pages = 0
    
    log_and_print(f"  Launching {len(ordered_images)} parallel transcription calls...")
    results = [None] * len(ordered_images)

    with ThreadPoolExecutor(max_workers=len(ordered_images)) as executor:
        future_to_index = {
            executor.submit(get_transcription, img_path, statement_text): j
            for j, img_path in enumerate(ordered_images)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            results[idx] = future.result()
            log_and_print(f"    ✅ Image {idx+1}/{len(ordered_images)} done: {os.path.basename(ordered_images[idx])}")

    for j, segment_text in enumerate(results):
        log_and_print(f"    Processing result {j+1}/{len(ordered_images)}")
        if not segment_text or segment_text.upper() == "NULL":
            consecutive_blank_pages += 1
            log_and_print(f"      -> Blank page detected! ({consecutive_blank_pages}/2 consecutive)")
            if consecutive_blank_pages >= 2:
                log_and_print(f"      -> 2 consecutive blank pages. Stopping.")
                break
            continue
        consecutive_blank_pages = 0
        full_text += segment_text + "\n\n"
    
    log_and_print(f"  ✅ Transcription complete. Total length: {len(full_text)} chars.")
    return full_text.strip()


# 2. Batch Execution Loop
def process_folder(input_folder, output_folder, temp_images_base, statement_text=""):
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(temp_images_base, exist_ok=True)
    
    # Grab all PDFs and sort them
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    pdf_files.sort()
    
    if not pdf_files:
        log_and_print(f"No PDF files found in {input_folder}")
        return

    # --- NOUVEAU : Pré-calcul pour la barre de progression --- 
    already_processed = []
    to_process = []
    
    for pdf_file in pdf_files:
        exam_id = os.path.splitext(pdf_file)[0]
        exam_output_base = os.path.join(output_folder, exam_id)
        if os.path.exists(exam_output_base + ".tex"):
            already_processed.append(pdf_file)
        else:
            to_process.append(pdf_file)

    log_and_print("-" * 50)
    log_and_print(f"STARTING BATCH PROCESS: Found {len(pdf_files)} total PDFs.")
    if already_processed:
        log_and_print(f"⏩ {len(already_processed)} files already transcribed. Resuming queue...")
    log_and_print("-" * 50)

    # Utilisation de tqdm avec "initial" et "total" pour une barre correcte dès la seconde 0
    with tqdm(total=len(pdf_files), initial=len(already_processed), desc="Batch Progress", unit="exam", colour="green") as pbar:
        for pdf_file in to_process:
            exam_id = os.path.splitext(pdf_file)[0] 
            pdf_path = os.path.join(input_folder, pdf_file)
            
            exam_output_base = os.path.join(output_folder, exam_id)
            exam_temp_folder = os.path.join(temp_images_base, exam_id)
            
            log_and_print(f"\n📄 Processing Exam: {pdf_file}")
            
            try:
                page_paths = pdf_to_images(pdf_path, output_folder=exam_temp_folder)
                ordered_images = build_transcription_order(page_paths, output_folder=exam_temp_folder)

                log_and_print("  Starting transcription...")
                full_text = ""
                consecutive_blank_pages = 0  # <--- NEW: Initialize blank page counter
                
                log_and_print(f"  Launching {len(ordered_images)} parallel transcription calls...")
                results = [None] * len(ordered_images)

                with ThreadPoolExecutor(max_workers=len(ordered_images)) as executor:
                    future_to_index = {
                        executor.submit(get_transcription, img_path, statement_text): j
                        for j, img_path in enumerate(ordered_images)
                    }
                    for future in as_completed(future_to_index):
                        idx = future_to_index[future]
                        results[idx] = future.result()
                        log_and_print(f"    ✅ Image {idx+1}/{len(ordered_images)} done: {os.path.basename(ordered_images[idx])}")

                for j, segment_text in enumerate(results):
                    log_and_print(f"    Processing result {j+1}/{len(ordered_images)}")
                    if not segment_text or segment_text.upper() == "NULL":
                        consecutive_blank_pages += 1
                        log_and_print(f"      -> Blank page detected! ({consecutive_blank_pages}/2 consecutive)")
                        if consecutive_blank_pages >= 2:
                            log_and_print(f"      -> 2 consecutive blank pages. Stopping.")
                            break
                        continue
                    consecutive_blank_pages = 0
                    full_text += segment_text + "\n\n"

                log_and_print("  Generating LaTeX document...")
                latex_document = build_latex_document(full_text)

                save_to_pdf(latex_document, exam_output_base)
                
                # Mise à jour manuelle de la barre de progression après un succès
                pbar.update(1)
                
            except Exception as e:
                # STOPPING EXECUTION ON ERROR
                log_and_print(f"\n❌ CRITICAL ERROR while processing {pdf_file}: {e}", is_error=True)
                log_and_print("Stopping the entire batch process to prevent further failures/quota drops.", is_error=True)
                break 

    log_and_print("\n" + "-" * 50)
    log_and_print("🏁 Batch process exited.")

if __name__ == "__main__":
    # Define your folders
    BASE_DIR = r"exams_data\INDP2A-SansNote Ingénierie"
    
    INPUT_DIR = os.path.join(BASE_DIR, r"PDFs")
    OUTPUT_DIR = os.path.join(BASE_DIR, "Transcriptions")
    TEMP_IMAGES_DIR = "extracted_images"
    STATEMENT_PATH = os.path.join(BASE_DIR, "exam_statement.pdf")

    full_statement_context = "" 

    # 1. Direct Extraction (Vertex AI Compatible)
    if os.path.exists(STATEMENT_PATH):
        log_and_print(f"📄 Found reference exam statement: {STATEMENT_PATH}")
        try:
            log_and_print("🔍 Extracting full statement text for transcription context...")
            
            # We pass the PATH directly now
            full_statement_context = extract_statement_text(STATEMENT_PATH)
            
            # --- LOGGING & DEBUGGING ---
            # Save to main log file
            logging.info("--- FULL EXTRACTED STATEMENT CONTEXT START ---")
            logging.info(full_statement_context)
            logging.info("--- FULL EXTRACTED STATEMENT CONTEXT END ---")

            # Save to the specific debug text file
            debug_path = os.path.join(BASE_DIR, "statement_verification_debug.txt")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(full_statement_context)
            
            log_and_print(f"✅ Statement grasped. Entire text logged and saved to: {debug_path}")
            log_and_print("-" * 50)
            log_and_print(f"Statement Preview: {full_statement_context[:250]}...")
            log_and_print("-" * 50)
            
        except Exception as e:
            log_and_print(f"⚠️ Failed to process exam statement: {e}", is_error=True)
            log_and_print("Continuing without context to avoid blocking the batch.")
    else:
        log_and_print(f"⚠️ Warning: Exam statement not found at {STATEMENT_PATH}. Running without context.", is_error=True)

    # 2. Start Processing
    process_folder(INPUT_DIR, OUTPUT_DIR, TEMP_IMAGES_DIR, full_statement_context)
