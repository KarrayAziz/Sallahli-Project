import os
import json
import re
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from json_safety import safe_json_loads

# 1. Setup Environment
load_dotenv()
PROJECT_ID = os.environ["PROJECT_ID"]
LOCATION = os.environ["LOCATION"]

# Initialize Vertex AI client (no API key needed if ADC is set up)
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

# Make sure to use Vertex-compatible model names
PRIMARY_MODEL = 'gemini-3.1-flash-lite-preview' 
FALLBACK_MODEL = 'gemini-3-flash-preview'


def _strip_json_fences(raw_text):
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _fallback_extract_answers(raw_text, expected_qids):
    """
    Last-resort parser for the student answer JSON object.

    Student answers can contain raw LaTeX backslashes and unescaped quotes
    copied from handwriting, so strict JSON may fail. The keys are known from
    the rubric; use them as anchors and preserve the answer text between keys.
    """
    text = _strip_json_fences(raw_text)
    extracted = {}

    positions = []
    for qid in expected_qids:
        match = re.search(rf'"{re.escape(qid)}"\s*:\s*"', text)
        if match:
            positions.append((qid, match.start(), match.end()))

    positions.sort(key=lambda item: item[1])
    for index, (qid, _start, value_start) in enumerate(positions):
        if index + 1 < len(positions):
            value_end = positions[index + 1][1]
            raw_value = text[value_start:value_end]
            raw_value = re.sub(r'"\s*,\s*$', "", raw_value, flags=re.DOTALL)
        else:
            raw_value = text[value_start:]
            raw_value = re.sub(r'"\s*}\s*$', "", raw_value, flags=re.DOTALL)
            raw_value = re.sub(r'"\s*,?\s*$', "", raw_value, flags=re.DOTALL)

        raw_value = raw_value.strip()
        raw_value = raw_value.replace(r"\n", "\n").replace(r"\t", "\t")
        raw_value = raw_value.replace(r"\"", '"').replace(r"\\", "\\")
        extracted[qid] = raw_value

    if not extracted:
        raise ValueError("Unable to recover student answers from malformed JSON.")

    print(f"  [JSON] Recovered {len(extracted)} answers from malformed student-answer JSON.", flush=True)
    return extracted


def parse_student_answer_json(raw_text, expected_qids):
    try:
        return safe_json_loads(raw_text, context="student answer extraction from text")
    except json.JSONDecodeError:
        return _fallback_extract_answers(raw_text, expected_qids)

def parse_student_transcription(pdf_path, output_json_path, rubric_path="master_rubric.json"):
    print(f"Uploading student transcription: {pdf_path}...")
    
    # --- NOUVEAUTÉ : LECTURE DES CLÉS EXACTES AVANT D'APPELER L'IA ---
    expected_qids = []
    if os.path.exists(rubric_path):
        with open(rubric_path, 'r', encoding='utf-8') as f:
            rubric = json.load(f)
        expected_qids = [item["question_id"] for item in rubric]
    else:
        print(f"❌ ERREUR: Le fichier {rubric_path} est introuvable. Il est nécessaire pour avoir les bonnes clés.")
        return

    # 2. Upload the PDF (Adapted for Vertex AI using Part.from_bytes)
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    student_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    
    # 3. Le Prompt mis à jour avec les clés injectées
    prompt = f"""
    Tu es un expert en extraction de données. Ton rôle est de lire la transcription d'une copie d'examen d'un étudiant et de la convertir en un dictionnaire JSON strict.

    RÈGLES D'EXTRACTION :
    1. Ignore les notes globales écrites au tout début du document.
    2. Identifie chaque réponse et associe-la à son numéro d'exercice et de question.
    3. RÈGLE ABSOLUE POUR LES CLÉS : Tu DOIS utiliser UNIQUEMENT les clés exactes de cette liste : {expected_qids}.
       - Ne crée AUCUNE autre clé. 
       - Si la copie de l'étudiant indique "5) a)", trouve la clé correspondante dans la liste (ex: "Ex1_Q5.a") et utilise l'orthographe exacte de la liste.
       - Ne regroupe pas les réponses. Si la liste demande "Ex1_Q5.a" et "Ex1_Q5.b", tu dois séparer le texte de l'étudiant en deux clés distinctes.
    4. RÈGLE POUR LE TEXTE (VALEURS) : La valeur associée à la clé doit être TOUT le texte de la réponse (incluant les descriptions d'images).
    5. Ne corrige pas les fautes d'orthographe de l'étudiant.

    RENVOIE UNIQUEMENT UN OBJET JSON VALIDE (Un dictionnaire simple {{clé: valeur}}).
    IMPORTANT : dans toutes les valeurs JSON, échappe chaque antislash avec un double antislash. Exemple : écris "\\\\frac{{x}}{{y}}" et jamais "\\frac{{x}}{{y}}".
    """

    model_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1
    )

    try:
        print(f"Parsing student answers with {PRIMARY_MODEL}...")
        response = client.models.generate_content(
            model=PRIMARY_MODEL,
            contents=[student_part, prompt],
            config=model_config
        )
    except genai_errors.APIError as e:
        print(f"⚠️ Primary model ({PRIMARY_MODEL}) encountered an error: {e}")
        print(f"🔄 Falling back to {FALLBACK_MODEL}...")
        response = client.models.generate_content(
            model=FALLBACK_MODEL,
            contents=[student_part, prompt],
            config=model_config
        )

    # 5. Process and fill blanks
    try:
        parsed_json = parse_student_answer_json(response.text, expected_qids)
        
        # Remplissage de sécurité strict
        final_json = {}
        for qid in expected_qids:
            if qid in parsed_json and parsed_json[qid] and parsed_json[qid].strip() != "":
                final_json[qid] = parsed_json[qid]
            else:
                final_json[qid] = "[Aucune réponse fournie par l'étudiant]"

        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, indent=4, ensure_ascii=False)
            
        print(f"\n✅ Success! Student answers mapped and saved locally to {output_json_path}")
        print(f"Total answers processed: {len(final_json)}")
        
    except json.JSONDecodeError:
        print("❌ Error: Gemini did not return valid JSON. Here is the raw output:")
        print(response.text)
        
    # Removed the finally block since Part.from_bytes doesn't leave files on the cloud that need deleting!

# --- API-friendly function (for FastAPI server) ---
def parse_student_answers_from_text(transcription_text, rubric_json):
    """
    Parses student answers from raw transcription text using the rubric structure.
    
    Args:
        transcription_text: The raw transcription string from OCR.
        rubric_json: Parsed rubric as a list of question dicts.
        
    Returns:
        dict: Mapping of question_id -> student answer text.
    """
    expected_qids = [item["question_id"] for item in rubric_json]
    
    prompt = f"""
    Tu es un expert en extraction de données. Ton rôle est de lire la transcription d'une copie d'examen d'un étudiant et de la convertir en un dictionnaire JSON strict.

    RÈGLES D'EXTRACTION :
    1. Ignore les notes globales écrites au tout début du document.
    2. Identifie chaque réponse et associe-la à son numéro d'exercice et de question.
    3. RÈGLE ABSOLUE POUR LES CLÉS : Tu DOIS utiliser UNIQUEMENT les clés exactes de cette liste : {expected_qids}.
       - Ne crée AUCUNE autre clé. 
       - Si la copie de l'étudiant indique "5) a)", trouve la clé correspondante dans la liste (ex: "Ex1_Q5.a") et utilise l'orthographe exacte de la liste.
       - Ne regroupe pas les réponses. Si la liste demande "Ex1_Q5.a" et "Ex1_Q5.b", tu dois séparer le texte de l'étudiant en deux clés distinctes.
    4. RÈGLE POUR LE TEXTE (VALEURS) : La valeur associée à la clé doit être TOUT le texte de la réponse (incluant les descriptions d'images).
    5. Ne corrige pas les fautes d'orthographe de l'étudiant.

    TRANSCRIPTION DE L'ÉTUDIANT :
    \"\"\"
    {transcription_text}
    \"\"\"

    RENVOIE UNIQUEMENT UN OBJET JSON VALIDE (Un dictionnaire simple {{clé: valeur}}).
    IMPORTANT : dans toutes les valeurs JSON, échappe chaque antislash avec un double antislash. Exemple : écris "\\\\frac{{x}}{{y}}" et jamais "\\frac{{x}}{{y}}".
    """
    
    model_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1
    )
    
    try:
        print(f"📝 Parsing student answers with {PRIMARY_MODEL}...")
        response = client.models.generate_content(
            model=PRIMARY_MODEL,
            contents=[prompt],
            config=model_config
        )
    except Exception as e:
        print(f"  ⚠️ {PRIMARY_MODEL} failed: {e}. Falling back to {FALLBACK_MODEL}...")
        response = client.models.generate_content(
            model=FALLBACK_MODEL,
            contents=[prompt],
            config=model_config
        )
    
    parsed_json = parse_student_answer_json(response.text, expected_qids)
    
    # Fill blanks for any missing questions
    final_json = {}
    for qid in expected_qids:
        if qid in parsed_json and parsed_json[qid] and parsed_json[qid].strip() != "":
            final_json[qid] = parsed_json[qid]
        else:
            final_json[qid] = "[Aucune réponse fournie par l'étudiant]"
    
    print(f"  ✅ Student answers parsed! {len(final_json)} answers mapped.")
    return final_json


if __name__ == "__main__":
    PDF_INPUT_PATH = "Transcription_Result.pdf"
    JSON_OUTPUT_PATH = "student_answers.json"
    RUBRIC_PATH = "master_rubric.json"
    
    if not os.path.exists(PDF_INPUT_PATH):
        print(f"File not found: {PDF_INPUT_PATH}")
    else:
        parse_student_transcription(PDF_INPUT_PATH, JSON_OUTPUT_PATH, RUBRIC_PATH)
