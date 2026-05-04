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
import base64
from typing import List

# Force UTF-8 encoding for stdout on Windows to prevent emoji print crashes
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Import our adapted modules
from Parallel_transcription import LATEX_MODEL, TRANSCRIPTION_MODEL, build_latex_document, save_to_pdf, transcribe_single_pdf, extract_statement_text
from rubric_parser import FALLBACK_MODEL as RUBRIC_FALLBACK_MODEL
from rubric_parser import PRIMARY_MODEL as RUBRIC_PRIMARY_MODEL
from rubric_parser import parse_rubric_from_bytes
from student_answer_parser import parse_student_answers_from_text
from API_Correction import MODEL_ID as CORRECTION_MODEL
from API_Correction import grade_exam, grade_exam_async

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


def make_thread_progress_callback(loop, queue, event_factory):
    def emit_progress(*callback_args):
        event = event_factory(*callback_args)
        loop.call_soon_threadsafe(queue.put_nowait, event)

    return emit_progress


async def drain_progress_until_done(task, queue):
    while not task.done():
        try:
            yield await asyncio.wait_for(queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            pass

    while not queue.empty():
        yield queue.get_nowait()


def log_model(step, model):
    print(f"[MODEL] {step}: {model}", flush=True)


def build_transcription_document(transcription_text, work_dir):
    """
    Builds a previewable PDF document from the OCR transcription.
    Returns raw text even if PDF compilation is unavailable.
    """
    output_base = os.path.join(work_dir, "transcribed_student_work")
    document = {
        "filename": "transcribed_student_work.pdf",
        "mime_type": "application/pdf",
        "pdf_base64": None,
        "raw_text": transcription_text,
    }

    try:
        log_model("transcription document", LATEX_MODEL)
        latex_content = build_latex_document(transcription_text)
        save_to_pdf(latex_content, output_base)

        pdf_path = output_base + ".pdf"
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                document["pdf_base64"] = base64.b64encode(f.read()).decode("ascii")
            print(f"[DOCUMENT] Transcription PDF generated: {pdf_path}", flush=True)
        else:
            print("[DOCUMENT] PDF compiler did not produce a transcription PDF; raw text preview will be used.", flush=True)
    except Exception as e:
        print(f"[DOCUMENT] Failed to generate transcription PDF: {e}", flush=True)

    return document


def write_file_bytes(path, content):
    with open(path, "wb") as f:
        f.write(content)


def parse_note_sur_20(value):
    try:
        return float(str(value).split("/")[0])
    except (ValueError, TypeError, IndexError):
        return 0.0


def build_batch_summary(batch_results):
    successful = [item for item in batch_results if item.get("status") == "completed"]
    failed = [item for item in batch_results if item.get("status") != "completed"]
    notes = [
        parse_note_sur_20(item.get("results", {}).get("BILAN_GLOBAL", {}).get("note_sur_20"))
        for item in successful
    ]
    average = round(sum(notes) / len(notes), 2) if notes else 0.0

    return {
        "total_files": len(batch_results),
        "completed": len(successful),
        "failed": len(failed),
        "average_note_sur_20": f"{average}/20",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


async def process_student_exam(
    file_payload,
    master_rubric,
    batch_semaphore,
    event_queue,
    loop,
    batch_work_dir,
):
    file_index = file_payload["file_index"]
    filename = file_payload["filename"]

    def exam_sse(step, message, progress, **extra):
        return sse(
            step,
            message,
            progress,
            file=filename,
            file_index=file_index,
            **extra,
        )

    async with batch_semaphore:
        work_dir = os.path.join(batch_work_dir, f"exam_{file_index}")
        os.makedirs(work_dir, exist_ok=True)

        try:
            event_queue.put_nowait(exam_sse("exam_started", "Traitement de la copie demarre.", 5))

            hw_path = os.path.join(work_dir, "handwritten.pdf")
            await asyncio.to_thread(write_file_bytes, hw_path, file_payload["content"])

            log_model(f"transcription [{filename}]", TRANSCRIPTION_MODEL)
            event_queue.put_nowait(exam_sse("transcription", "Transcription OCR en cours...", 10))

            temp_images_dir = os.path.join(work_dir, "images")
            transcription_callback = make_thread_progress_callback(
                loop,
                event_queue,
                lambda completed, total, image_name: exam_sse(
                    "transcription_progress",
                    f"Transcription OCR: {completed}/{total} pages traitees",
                    10 + round((completed / max(total, 1)) * 25),
                    step_progress=round((completed / max(total, 1)) * 100),
                    step_completed=completed,
                    step_total=total,
                    step_label="Transcription OCR",
                    item=image_name,
                ),
            )
            transcription_text = await asyncio.to_thread(
                transcribe_single_pdf,
                hw_path,
                "",
                temp_images_dir,
                progress_callback=transcription_callback,
            )

            if not transcription_text or len(transcription_text.strip()) < 10:
                raise ValueError("La transcription est vide. Le PDF ne semble pas contenir d'ecriture manuscrite lisible.")

            event_queue.put_nowait(
                exam_sse(
                    "transcription_done",
                    f"Transcription terminee ({len(transcription_text)} caracteres)",
                    35,
                )
            )

            event_queue.put_nowait(exam_sse("transcription_document", "Generation du document transcrit...", 37))
            transcription_document = await asyncio.to_thread(
                build_transcription_document,
                transcription_text,
                work_dir,
            )

            event_queue.put_nowait(exam_sse("parsing", "Extraction des reponses de l'etudiant...", 60))
            student_answers = await asyncio.to_thread(
                parse_student_answers_from_text,
                transcription_text,
                master_rubric,
            )
            event_queue.put_nowait(
                exam_sse("parsing_done", f"Reponses extraites ({len(student_answers)} reponses)", 70)
            )

            log_model(f"correction [{filename}]", CORRECTION_MODEL)
            event_queue.put_nowait(exam_sse("grading", "Correction par l'IA en cours...", 75))

            def grading_callback(q_id, score, max_score, completed, total):
                event_queue.put_nowait(
                    exam_sse(
                        "grading_progress",
                        f"Correction IA: {completed}/{total} questions corrigees",
                        75 + round((completed / max(total, 1)) * 20),
                        step_progress=round((completed / max(total, 1)) * 100),
                        step_completed=completed,
                        step_total=total,
                        step_label="Correction par l'IA",
                        item=q_id,
                        score=score,
                        max_score=max_score,
                    )
                )

            grading_results = await grade_exam_async(
                master_rubric,
                student_answers,
                progress_callback=grading_callback,
            )
            grading_results["TRANSCRIPTION_DOCUMENT"] = transcription_document

            event_queue.put_nowait(exam_sse("exam_complete", "Copie corrigee.", 100))
            return {
                "file": filename,
                "file_index": file_index,
                "status": "completed",
                "results": grading_results,
            }

        except Exception as e:
            error_msg = str(e)
            print(f"Pipeline error for {filename}: {error_msg}", flush=True)
            event_queue.put_nowait(exam_sse("exam_error", f"Erreur: {error_msg}", 0, error=error_msg))
            return {
                "file": filename,
                "file_index": file_index,
                "status": "error",
                "error": error_msg,
            }


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "sallahli-ai"}


@app.post("/api/analyze")
async def analyze_exam_batch(
    handwritten_work: List[UploadFile] = File(..., description="Student handwritten exam PDFs"),
    rubric: UploadFile = File(..., description="Official rubric/correction PDF"),
):
    """
    Batch AI correction pipeline.
    Parses the rubric once, then processes multiple student PDFs concurrently.
    """
    if not handwritten_work:
        raise HTTPException(status_code=400, detail="Au moins une copie manuscrite PDF est requise.")

    for upload in handwritten_work:
        if not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Copie manuscrite: PDF requis. Recu: {upload.filename}",
            )
    if not rubric.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=f"Bareme: PDF requis. Recu: {rubric.filename}")

    handwritten_payloads = [
        {
            "file_index": i,
            "filename": upload.filename,
            "content": await upload.read(),
        }
        for i, upload in enumerate(handwritten_work)
    ]
    rubric_bytes = await rubric.read()

    async def event_stream():
        work_dir = tempfile.mkdtemp(prefix="sallahli_batch_")

        try:
            yield sse(
                "batch_started",
                f"{len(handwritten_payloads)} copie(s) recue(s). Analyse du bareme...",
                5,
                total_files=len(handwritten_payloads),
            )

            log_model("rubric parsing", f"primary={RUBRIC_PRIMARY_MODEL}, fallback={RUBRIC_FALLBACK_MODEL}")
            yield sse("rubric", "Analyse du bareme en cours...", 10, total_files=len(handwritten_payloads))
            master_rubric = await asyncio.to_thread(
                parse_rubric_from_bytes,
                rubric_bytes,
                rubric.filename,
            )
            yield sse(
                "rubric_done",
                f"Bareme analyse ({len(master_rubric)} questions detectees). Lancement du batch...",
                15,
                total_files=len(handwritten_payloads),
            )

            loop = asyncio.get_running_loop()
            event_queue = asyncio.Queue()
            batch_semaphore = asyncio.Semaphore(3)
            tasks = [
                asyncio.create_task(
                    process_student_exam(
                        payload,
                        master_rubric,
                        batch_semaphore,
                        event_queue,
                        loop,
                        work_dir,
                    )
                )
                for payload in handwritten_payloads
            ]

            pending = set(tasks)
            while pending:
                done, pending = await asyncio.wait(
                    pending,
                    timeout=0.1,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                while not event_queue.empty():
                    yield event_queue.get_nowait()

            while not event_queue.empty():
                yield event_queue.get_nowait()

            batch_results = await asyncio.gather(*tasks)
            batch_results.sort(key=lambda item: item.get("file_index", 0))
            summary = build_batch_summary(batch_results)

            yield sse(
                "complete",
                "Analyse batch complete !",
                100,
                results={
                    "BATCH_RESULTS": batch_results,
                    "BILAN_BATCH": summary,
                },
            )

        except Exception as e:
            error_msg = str(e)
            print(f"Batch pipeline error: {error_msg}", flush=True)
            yield sse("error", f"Erreur du serveur: {error_msg}", 0)

        finally:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/analyze-legacy")
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
            log_model("transcription", TRANSCRIPTION_MODEL)
            yield sse("transcription", "Transcription OCR en cours... (cela peut prendre 1-2 minutes)", 10)
            
            temp_images_dir = os.path.join(work_dir, "images")
            loop = asyncio.get_running_loop()
            transcription_queue = asyncio.Queue()
            transcription_callback = make_thread_progress_callback(
                loop,
                transcription_queue,
                lambda completed, total, image_name: sse(
                    "transcription_progress",
                    f"Transcription OCR: {completed}/{total} pages traitées",
                    10 + round((completed / max(total, 1)) * 25),
                    step_progress=round((completed / max(total, 1)) * 100),
                    step_completed=completed,
                    step_total=total,
                    step_label="Transcription OCR",
                    item=image_name,
                ),
            )
            transcription_task = asyncio.create_task(
                asyncio.to_thread(
                    transcribe_single_pdf,
                    hw_path,
                    "",
                    temp_images_dir,
                    progress_callback=transcription_callback,
                )
            )
            async for progress_event in drain_progress_until_done(transcription_task, transcription_queue):
                yield progress_event
            transcription_text = await transcription_task
            
            if not transcription_text or len(transcription_text.strip()) < 10:
                yield sse("error", "La transcription est vide. Le PDF ne semble pas contenir d'écriture manuscrite lisible.", 0)
                return
            
            msg = f"Transcription terminée ({len(transcription_text)} caractères)"
            yield sse("transcription_done", msg, 35)

            # --- Step 2b: Build preview document from transcription ---
            yield sse("transcription_document", "Génération du document transcrit...", 37)
            transcription_document = await asyncio.to_thread(
                build_transcription_document, transcription_text, work_dir
            )
            
            # --- Step 3: Parse the rubric ---
            log_model("rubric parsing", f"primary={RUBRIC_PRIMARY_MODEL}, fallback={RUBRIC_FALLBACK_MODEL}")
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
            log_model("correction", CORRECTION_MODEL)
            yield sse("grading", "Correction par l'IA en cours... (cela peut prendre 1-3 minutes)", 75)
            
            grading_queue = asyncio.Queue()
            grading_callback = make_thread_progress_callback(
                loop,
                grading_queue,
                lambda q_id, score, max_score, completed, total: sse(
                    "grading_progress",
                    f"Correction IA: {completed}/{total} questions corrigées",
                    75 + round((completed / max(total, 1)) * 20),
                    step_progress=round((completed / max(total, 1)) * 100),
                    step_completed=completed,
                    step_total=total,
                    step_label="Correction par l'IA",
                    item=q_id,
                ),
            )
            grading_task = asyncio.create_task(
                asyncio.to_thread(
                    grade_exam,
                    master_rubric,
                    student_answers,
                    progress_callback=grading_callback,
                )
            )
            async for progress_event in drain_progress_until_done(grading_task, grading_queue):
                yield progress_event
            grading_results = await grading_task
            
            yield sse("grading_done", "Correction terminée !", 95)
            
            # --- Step 6: Send final results ---
            grading_results["TRANSCRIPTION_DOCUMENT"] = transcription_document
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
        log_model("transcription", TRANSCRIPTION_MODEL)
        transcription_text = transcribe_single_pdf(hw_path, "", temp_images_dir)
        transcription_document = build_transcription_document(transcription_text, work_dir)
        log_model("rubric parsing", f"primary={RUBRIC_PRIMARY_MODEL}, fallback={RUBRIC_FALLBACK_MODEL}")
        master_rubric = parse_rubric_from_bytes(rubric_bytes, rubric.filename)
        student_answers = parse_student_answers_from_text(transcription_text, master_rubric)
        log_model("correction", CORRECTION_MODEL)
        grading_results = grade_exam(master_rubric, student_answers)
        grading_results["TRANSCRIPTION_DOCUMENT"] = transcription_document
        
        return JSONResponse(content=grading_results)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
