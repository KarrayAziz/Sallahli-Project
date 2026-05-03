import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types      


# 1. Setup Environment
load_dotenv()
PROJECT_ID = "gen-lang-client-0125580043"
LOCATION = "global"
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

# Make sure to use Vertex-compatible model names here
PRIMARY_MODEL = 'gemini-3.1-flash-lite-preview' # Update with exact Vertex model ID if needed
FALLBACK_MODEL = 'gemini-3-flash-preview'


def response_text_or_raise(response, model_name):
    """Extracts text from a Gemini response and fails with a useful error if it is empty."""
    text = getattr(response, "text", None)
    if text:
        return text

    candidates = getattr(response, "candidates", None) or []
    if candidates:
        finish_reason = getattr(candidates[0], "finish_reason", None)
        safety_ratings = getattr(candidates[0], "safety_ratings", None)
        raise ValueError(
            f"{model_name} returned no text. finish_reason={finish_reason}, safety_ratings={safety_ratings}"
        )

    raise ValueError(f"{model_name} returned no text and no candidates.")


def parse_json_response(response, model_name):
    raw_text = response_text_or_raise(response, model_name)
    return json.loads(raw_text)

def parse_rubric_pdf(pdf_path, output_json_path):
    print(f"Uploading official rubric PDF: {pdf_path}...")
    
    # 2. Upload the PDF to Gemini (Fixed the file reading context)
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    
    # 3. The Strict JSON Prompt
    prompt = """
    Tu es un assistant d'extraction de données strict. Ton SEUL rôle est de copier-coller et de structurer le texte exact du corrigé PDF fourni. 
    TU NE DOIS JAMAIS reformuler, résumer, interpréter ou inventer des réponses modèles. Tu dois utiliser les mots exacts du document.

    Pour CHAQUE question trouvée dans le document, extrais :
    1. "question_id" : L'identifiant de la question. 
       - RÈGLE ABSOLUE : L'identifiant DOIT inclure le numéro de l'exercice. Format obligatoire : "Ex[Numéro Exercice]_Q[Numéro/Lettre Question]". 
       - Exemples : "Ex1_Q1", "Ex1_Q3.a", "Ex2_Q1", "Ex3_QII.1".
    2. "context" : Le texte d'introduction global de l'exercice (description du dataset, liste des variables, etc.). 
       - RÈGLE ABSOLUE : Ce champ NE DOIT PAS être null si l'exercice possède une introduction. Tu DOIS copier et répéter l'introduction complète de l'exercice pour TOUTES les questions qui appartiennent à cet exercice. (Exemple: Pour les questions 1, 2, et 3, tu dois coller la description complète du jeu de données dans le context de CHACUNE de ces questions).
       - RÈGLE POUR LES TABLEAUX : Si le contexte contient un tableau, tu DOIS obligatoirement le formater en Markdown (avec les symboles `|` et `-`).
    3. "question_text" : UNIQUEMENT la phrase de la question exacte qui a été posée à l'étudiant. 
       - RÈGLE POUR LES SOUS-QUESTIONS : Si c'est une sous-question (ex: 3.a, 3.b), tu DOIS concaténer le texte de la question parente avec le texte de la sous-question.
    4. "max_score" : Le score total de la question (float).
    5. "criteria" : Un tableau d'objets définissant le barème détaillé. 
       - RÈGLE ABSOLUE DE SÉPARATION : Tu DOIS obligatoirement séparer le texte de la condition et la valeur des points en DEUX clés distinctes : "condition" (string) et "points" (float).
       - RÈGLE POUR LES LISTES À PUCES ET BLOCS GLOBAUX : Si le corrigé indique un score global (ex: "1 pt") suivi de plusieurs tirets, puces, formules mathématiques ou explications SANS points spécifiques pour chaque ligne, tu DOIS regrouper TOUT ce texte en UNE SEULE "condition" valant ce score global. 
       - RÈGLE ANTI-INVENTION (CRITIQUE) : NE DIVISE JAMAIS les points toi-même. N'invente JAMAIS des scores comme 0.33, 0.34 ou 0.0. Si les points partiels ne sont pas explicitement écrits dans le texte, regroupe tout sous le score global.
       - RÈGLE D'EXHAUSTIVITÉ (SAUTS DE PAGE) : Une correction peut s'étaler sur plusieurs paragraphes ou traverser un saut de page (ex: de la page 4 à la page 5). Tu DOIS capturer l'intégralité de la correction (incluant toutes les formules de covariance, variance, etc.) jusqu'à ce que tu rencontres la question suivante. Ne tronque pas la réponse.
       - Le texte des points (ex: "0.25 pt", "1 pt") NE DOIT JAMAIS être inclus dans la chaîne "condition".
       - ATTENTION AUX FUSIONS DE TEXTE : Si le texte dit "nbre d'occurrences 4 0.25 pt", la condition est "...nbre d'occurrences 4" et les points sont 0.25. Ne fusionne jamais les chiffres pour créer des aberrations comme "40.25".
       - RÈGLE D'EXCLUSION : Ne crée un critère QUE s'il y a des points associés. S'il y a une phrase d'introduction sans points (ex: "En considérant l'histogramme :"), intègre-la au critère suivant ou ignore-la. 

    Voici la structure EXACTE requise pour les critères :
    "criteria": [
        {
            "condition": "La largeur commune des bins est 50-10/N=8 => on aura 5 bins",
            "points": 0.25
        },
        {
            "condition": "[10 - 18[ (10, 13, 14, 15) => nbre d'occurrences 4",
            "points": 0.25
        }
    ]
    RENVOIE UNIQUEMENT UN TABLEAU JSON VALIDE.
    """

    # 4. Generate the Structured Content with fallback
    model_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1
    )   

    active_model = PRIMARY_MODEL
    try:
        print(f"Parsing rubric with {PRIMARY_MODEL} (This may take 30-60 seconds)...")
        response = client.models.generate_content(
            model=PRIMARY_MODEL,
            contents=[pdf_part, prompt], # Changed rubric_file to pdf_part
            config=model_config
        )
    except genai_errors.APIError as e: # Updated to broader error catch for the new SDK
        if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e):
            print(f"    {PRIMARY_MODEL} unavailable. Falling back to {FALLBACK_MODEL}...")
            active_model = FALLBACK_MODEL
            response = client.models.generate_content(
                model=FALLBACK_MODEL,
                contents=[pdf_part, prompt], # Changed rubric_file to pdf_part
                config=model_config
            )
        else:
            raise

    # 5. Clean up the response and save it
    try:
        parsed_json = parse_json_response(response, active_model)
        
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(parsed_json, f, indent=4, ensure_ascii=False)
            
        print(f"\n✅ Success! Structured rubric saved locally to {output_json_path}")
        print(f"Total questions parsed: {len(parsed_json)}")
        
    except json.JSONDecodeError:
        print("❌ Error: Gemini did not return valid JSON. Here is the raw output:")
        print(response.text)
        
    # Removed the legacy finally block: Part.from_bytes does not upload stateful files, so there is nothing to delete.

# --- API-friendly function (for FastAPI server) ---
def parse_rubric_from_bytes(pdf_bytes, filename="rubric.pdf"):
    """
    Parses a rubric PDF from raw bytes and returns the structured JSON.
    Uses the Gemini Files API for upload, then deletes after processing.
    
    Args:
        pdf_bytes: Raw bytes of the rubric PDF.
        filename: Original filename (for logging).
        
    Returns:
        list: Parsed rubric as a list of question dicts.
    """
    print(f"📋 Parsing rubric: {filename}...")

    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        
    prompt = """
    Tu es un assistant d'extraction de données strict. Ton SEUL rôle est de copier-coller et de structurer le texte exact du corrigé PDF fourni. 
    TU NE DOIS JAMAIS reformuler, résumer, interpréter ou inventer des réponses modèles. Tu dois utiliser les mots exacts du document.

    Pour CHAQUE question trouvée dans le document, extrais :
    1. "question_id" : L'identifiant de la question. 
       - RÈGLE ABSOLUE : L'identifiant DOIT inclure le numéro de l'exercice. Format obligatoire : "Ex[Numéro Exercice]_Q[Numéro/Lettre Question]". 
       - Exemples : "Ex1_Q1", "Ex1_Q3.a", "Ex2_Q1", "Ex3_QII.1".
    2. "context" : Le texte d'introduction global de l'exercice (description du dataset, liste des variables, etc.). 
       - RÈGLE ABSOLUE : Ce champ NE DOIT PAS être null si l'exercice possède une introduction. Tu DOIS copier et répéter l'introduction complète de l'exercice pour TOUTES les questions qui appartiennent à cet exercice.
       - RÈGLE POUR LES TABLEAUX : Si le contexte contient un tableau, tu DOIS obligatoirement le formater en Markdown (avec les symboles `|` et `-`).
    3. "question_text" : UNIQUEMENT la phrase de la question exacte qui a été posée à l'étudiant. 
       - RÈGLE POUR LES SOUS-QUESTIONS : Si c'est une sous-question (ex: 3.a, 3.b), tu DOIS concaténer le texte de la question parente avec le texte de la sous-question.
    4. "max_score" : Le score total de la question (float).
    5. "criteria" : Un tableau d'objets définissant le barème détaillé. 
       - RÈGLE ABSOLUE DE SÉPARATION : Tu DOIS obligatoirement séparer le texte de la condition et la valeur des points en DEUX clés distinctes : "condition" (string) et "points" (float).
       - RÈGLE POUR LES LISTES À PUCES ET BLOCS GLOBAUX : Si le corrigé indique un score global (ex: "1 pt") suivi de plusieurs tirets, puces, formules mathématiques ou explications SANS points spécifiques pour chaque ligne, tu DOIS regrouper TOUT ce texte en UNE SEULE "condition" valant ce score global. 
       - RÈGLE ANTI-INVENTION (CRITIQUE) : NE DIVISE JAMAIS les points toi-même. N'invente JAMAIS des scores comme 0.33, 0.34 ou 0.0. Si les points partiels ne sont pas explicitement écrits dans le texte, regroupe tout sous le score global.
       - RÈGLE D'EXHAUSTIVITÉ (SAUTS DE PAGE) : Une correction peut s'étaler sur plusieurs paragraphes ou traverser un saut de page. Tu DOIS capturer l'intégralité de la correction jusqu'à ce que tu rencontres la question suivante. Ne tronque pas la réponse.
       - Le texte des points (ex: "0.25 pt", "1 pt") NE DOIT JAMAIS être inclus dans la chaîne "condition".
       - ATTENTION AUX FUSIONS DE TEXTE : Si le texte dit "nbre d'occurrences 4 0.25 pt", la condition est "...nbre d'occurrences 4" et les points sont 0.25.
       - RÈGLE D'EXCLUSION : Ne crée un critère QUE s'il y a des points associés.

    Voici la structure EXACTE requise pour les critères :
    "criteria": [
        {
            "condition": "La largeur commune des bins est 50-10/N=8 => on aura 5 bins",
            "points": 0.25
        },
        {
            "condition": "[10 - 18[ (10, 13, 14, 15) => nbre d'occurrences 4",
            "points": 0.25
        }
    ]
    RENVOIE UNIQUEMENT UN TABLEAU JSON VALIDE.
    """
        
    # Fixed: config must be a types.GenerateContentConfig object, not a dict
    model_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1
    )
    
    active_model = PRIMARY_MODEL
    try:
        print(f"  Parsing with {PRIMARY_MODEL}...")
        response = client.models.generate_content(
            model=PRIMARY_MODEL,
            contents=[pdf_part, prompt], # Changed rubric_file to pdf_part
            config=model_config
        )
        parsed_json = parse_json_response(response, PRIMARY_MODEL)
    except Exception as e:
        print(f"  ⚠️ {PRIMARY_MODEL} failed: {e}. Falling back to {FALLBACK_MODEL}...")
        active_model = FALLBACK_MODEL
        response = client.models.generate_content(
            model=FALLBACK_MODEL,
            contents=[pdf_part, prompt], # Changed rubric_file to pdf_part
            config=model_config
        )
        parsed_json = parse_json_response(response, FALLBACK_MODEL)

    print(f"  ✅ Rubric parsed with {active_model}! {len(parsed_json)} questions found.")
    
    return parsed_json

    # Removed the legacy finally block: No temp files are created with Part.from_bytes


# --- EXECUTE ---
if __name__ == "__main__":
    # Point this to where your Corrigé PDF actually lives on your PC
    PDF_INPUT_PATH = "Correction\\Corrigé_ingénierie_données_2025.pdf"
    JSON_OUTPUT_PATH = "master_rubric.json"
    
    # Create the exam_papers folder if it doesn't exist to prevent errors
    if not os.path.exists("exam_papers"):
        print("Creating 'exam_papers' folder. Please place your PDF inside it and run again.")
        os.makedirs("exam_papers")
    elif not os.path.exists(PDF_INPUT_PATH):
        print(f"File not found: {PDF_INPUT_PATH}. Please make sure the PDF is in the correct folder.")
    else:
        parse_rubric_pdf(PDF_INPUT_PATH, JSON_OUTPUT_PATH)
