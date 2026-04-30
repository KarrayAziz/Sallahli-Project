import os
import json
from dotenv import load_dotenv
from google import genai

# 1. Setup Environment
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found. Please check your .env file.")

client = genai.Client(api_key=api_key)

PRIMARY_MODEL = 'gemini-3-flash-preview'
FALLBACK_MODEL = 'gemini-2.5-flash'

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

    # 2. Upload the PDF
    with open(pdf_path, "rb") as f:
        student_file = client.files.upload(
            file=f,
            config={'mime_type': 'application/pdf'}
        )
    
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
    """

    try:
        print(f"Parsing student answers with {PRIMARY_MODEL}...")
        response = client.models.generate_content(
            model=PRIMARY_MODEL,
            contents=[student_file, prompt],
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1 
            }
        )
    except Exception as e:
        print(f"⚠️ Primary model ({PRIMARY_MODEL}) encountered an error: {e}")
        print(f"🔄 Falling back to {FALLBACK_MODEL}...")
        response = client.models.generate_content(
            model=FALLBACK_MODEL,
            contents=[student_file, prompt],
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1 
            }
        )

    # 5. Process and fill blanks
    try:
        parsed_json = json.loads(response.text)
        
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
        
    finally:
        print("Cleaning up file from cloud...")
        client.files.delete(name=student_file.name)

if __name__ == "__main__":
    PDF_INPUT_PATH = "Transcription_Result.pdf"
    JSON_OUTPUT_PATH = "student_answers.json"
    RUBRIC_PATH = "master_rubric.json"
    
    if not os.path.exists(PDF_INPUT_PATH):
        print(f"File not found: {PDF_INPUT_PATH}")
    else:
        parse_student_transcription(PDF_INPUT_PATH, JSON_OUTPUT_PATH, RUBRIC_PATH)