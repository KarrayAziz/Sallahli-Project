"""
Sallahli AI Service — FastAPI Server
Orchestrates: OCR Transcription → Rubric Parsing → Answer Extraction → AI Grading
"""

import os
import sys
import json
import time
import shutil
import tempfile
import asyncio

# Force UTF-8 encoding for stdout on Windows to prevent emoji print crashes
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Import our adapted modules
from Parallel_transcription import transcribe_single_pdf, extract_statement_text
from rubric_parser import parse_rubric_from_bytes
from student_answer_parser import parse_student_answers_from_text
from API_Correction import grade_exam

app = FastAPI(
    title="Sallahli AI Service",
    description="AI-powered exam correction pipeline",
    version="1.0.0"
)

# CORS — allow the Next.js frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sse(step, message, progress, **extra):
    """Build an SSE data line safely (avoids f-string backslash issues)."""
    payload = {"step": step, "message": message, "progress": progress}
    payload.update(extra)
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "sallahli-ai"}


@app.post("/api/analyze")
async def analyze_exam(
    handwritten_work: UploadFile = File(..., description="Student's handwritten exam PDF"),
    rubric: UploadFile = File(..., description="Official rubric/correction PDF"),
):
    """
    Full AI correction pipeline.
    Accepts two PDF files and returns grading results with BILAN_GLOBAL.
    Streams progress updates via Server-Sent Events (SSE).
    """
    
    # Validate file types
    for upload, label in [(handwritten_work, "Copie manuscrite"), (rubric, "Barème")]:
        if not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"{label}: Le fichier doit être un PDF. Reçu: {upload.filename}"
            )
    
    # Read file bytes upfront
    handwritten_bytes = await handwritten_work.read()
    rubric_bytes = await rubric.read()
    
    async def event_stream():
        """Generator that yields SSE events as the pipeline progresses."""
        work_dir = tempfile.mkdtemp(prefix="sallahli_job_")
        
        try:
            # --- Step 1: Save handwritten PDF to disk (needed for pdf2image) ---
            yield sse("upload", "Fichiers reçus. Démarrage du pipeline...", 5)
            
            hw_path = os.path.join(work_dir, "handwritten.pdf")
            with open(hw_path, "wb") as f:
                f.write(handwritten_bytes)
            
            # --- Step 2: Transcribe the handwritten exam ---
            yield sse("transcription", "Transcription OCR en cours... (cela peut prendre 1-2 minutes)", 10)
            
            temp_images_dir = os.path.join(work_dir, "images")
            transcription_text = await asyncio.to_thread(
                transcribe_single_pdf, hw_path, "", temp_images_dir
            )
            
            if not transcription_text or len(transcription_text.strip()) < 10:
                yield sse("error", "La transcription est vide. Le PDF ne semble pas contenir d'écriture manuscrite lisible.", 0)
                return
            
            msg = f"Transcription terminée ({len(transcription_text)} caractères)"
            yield sse("transcription_done", msg, 35)
            
            # --- Step 3: Parse the rubric ---
            yield sse("rubric", "Analyse du barème en cours...", 40)
            
            master_rubric = await asyncio.to_thread(
                parse_rubric_from_bytes, rubric_bytes, rubric.filename
            )
            
            msg = f"Barème analysé ({len(master_rubric)} questions détectées)"
            yield sse("rubric_done", msg, 55)
            
            # --- Step 4: Parse student answers from transcription ---
            yield sse("parsing", "Extraction des réponses de l'étudiant...", 60)
            
            student_answers = await asyncio.to_thread(
                parse_student_answers_from_text, transcription_text, master_rubric
            )
            
            msg = f"Réponses extraites ({len(student_answers)} réponses)"
            yield sse("parsing_done", msg, 70)
            
            # --- Step 5: Grade with AI ---
            yield sse("grading", "Correction par l'IA en cours... (cela peut prendre 1-3 minutes)", 75)
            
            grading_results = await asyncio.to_thread(
                grade_exam, master_rubric, student_answers
            )
            
            yield sse("grading_done", "Correction terminée !", 95)
            
            # --- Step 6: Send final results ---
            yield sse("complete", "Analyse complète !", 100, results=grading_results)
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Pipeline error: {error_msg}")
            yield sse("error", f"Erreur du serveur: {error_msg}", 0)
            
        finally:
            # Clean up temp files
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/analyze-sync")
async def analyze_exam_sync(
    handwritten_work: UploadFile = File(...),
    rubric: UploadFile = File(...),
):
    """
    Synchronous version — returns full JSON at once (for simpler clients).
    """
    for upload, label in [(handwritten_work, "Copie manuscrite"), (rubric, "Barème")]:
        if not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"{label}: PDF requis.")
    
    handwritten_bytes = await handwritten_work.read()
    rubric_bytes = await rubric.read()
    work_dir = tempfile.mkdtemp(prefix="sallahli_job_")
    
    try:
        hw_path = os.path.join(work_dir, "handwritten.pdf")
        with open(hw_path, "wb") as f:
            f.write(handwritten_bytes)
        
        temp_images_dir = os.path.join(work_dir, "images")
        transcription_text = transcribe_single_pdf(hw_path, "", temp_images_dir)
        master_rubric = parse_rubric_from_bytes(rubric_bytes, rubric.filename)
        student_answers = parse_student_answers_from_text(transcription_text, master_rubric)
        grading_results = grade_exam(master_rubric, student_answers)
        
        return JSONResponse(content=grading_results)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
