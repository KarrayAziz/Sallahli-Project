import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types      
from json_safety import safe_json_loads
from examRubric import ExamRubric
import re
from validation_tests import *

# 1. Setup Environment
load_dotenv()
PROJECT_ID = os.environ["PROJECT_ID"]
LOCATION = os.environ["LOCATION"]

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

FIRST_PRIMARY_MODEL = 'gemini-2.5-flash' 
FIRST_FALLBACK_MODEL = 'gemini-2.5-flash'

SECOND_PRIMARY_MODEL = 'gemini-2.5-flash'
SECOND_FALLBACK_MODEL = 'gemini-2.5-flash'

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




def parse_json_response_safely(response, model_name):
    # """
    # Extract text from gemini and apply the following json loads

    # test_input = r'''
    # {
    # "question": "Solve this equation: \alpha + \beta = 5",
    # "hint": "Use formula \frac{a}{b} and remember \n is newline",
    # "bad_escape": "This is invalid: \q \x \y",
    # "unicode_test": "Smile: \u263A and broken: \u12GZ",
    # "mixed": "Math: \alpha \beta \gamma and quote: \"hello\""
    # }
    # '''

    # output : 
    # {
    # "question": "Solve this equation: \\alpha + \\beta = 5",
    # "hint": "Use formula \\frac{a}{b} and remember \n is newline",
    # "bad_escape": "This is invalid: \\q \\x \\y",
    # "unicode_test": "Smile: \u263A and broken: \\u12GZ",
    # "mixed": "Math: \\alpha \\beta \\gamma and quote: \\"hello\""
    # }
    # """

    raw_text = response_text_or_raise(response, model_name)
    return safe_json_loads(raw_text, context=f"rubric parsing with {model_name}")



def parse_json_response(response, model_name):
    """
    Extract text from gemini 
    """

    raw_text = response_text_or_raise(response, model_name)
    return raw_text




def parse_rubric_pdf(pdf_path, output_json_path, output_json_path_safely):
    """
    Le format utilisé dans le prompt est le suivant :

    [Retour de Validation]
            ↓
    [Grammaire du Barème]
            ↓
    [Règles de Formatage]
            ↓
    [Exemples Corrects]
            ↓
    [Exemples Incorrects]
            ↓            
    [Document PDF à Analyser]
            ↓
    [Schéma de Sortie]
    """
    print(f"Uploading official rubric PDF: {pdf_path}...")
    
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")

    #PROMPT TO GEMINI

    prompt = ""
    prompt += "[GRAMMAIRE D'EXTRACTION DU BARÈME]\n"
    prompt += r"""

Pour CHAQUE question trouvée dans le document, extrais :
1. "question_id" : L'identifiant de la question. 
   - RÈGLE ABSOLUE : L'identifiant DOIT inclure le numéro de l'exercice, le numéro de la question, le numéro de la partie de l'exercice(s'il existe), le numéro de la sous question(s'il existe), Format obligatiore :
        -Format générale : "Ex[Numéro Exercice]_Q[Numéro/Lettre Question]"
        -S'il y a une sous question : "Ex[Numéro Exercice]_Q[Numéro/Lettre Question].[Numéro/Lettre de sous Question]" 
        -Si l'exercice contient plusieurs parties : ""Ex[Numéro Exercice]_Partie[Numéro de la partie]_Q[Numéro/Lettre Question]" 
        -Si l'exercice contient plusieurs parties et une sous question : ""Ex[Numéro Exercice]_Partie[Numéro de la partie]_Q[Numéro/Lettre Question].[Numéro/Lettre de sous Question]" 
   - Exemples : "Ex1_Q1", "Ex1_Q3.a", "Ex3_QII.1", "Ex5_Q1.a", "Ex3_PartieI_Q4", "Ex3_PartieI_Q4.a".
2. "context" : Le texte d'introduction global de l'exercice. 
   - RÈGLE ABSOLUE : Ce champ NE DOIT PAS être null si l'exercice possède une introduction. Tu DOIS copier et répéter l'introduction complète de l'exercice pour TOUTES les questions qui appartiennent à cet exercice. (Exemple: Pour les questions 1, 2, et 3, tu dois coller la description complète du jeu de données dans le context de CHACUNE de ces questions).
3. "question_text" : UNIQUEMENT la phrase de la question exacte qui a été posée à l'étudiant. 
   - RÈGLE POUR LES SOUS-QUESTIONS : Si c'est une sous-question (ex: 3.a, 3.b), tu DOIS concaténer le texte de la question parente avec le texte de la sous-question.
4. "max_score" : Le score total de la question (float).
5. "critère" : Un tableau d'objets définissant le barème détaillé.

[DÉFINITION FONDAMENTALE]
Un "critère" représente une unité de notation (bloc de score), et non une étape, une phrase, un exemple ou une solution individuelle.

[RÈGLE PRINCIPALE]
Toutes les réponses possibles qui correspondent à une même question et qui partagent le même score DOIVENT être regroupées dans UN SEUL critère.

[CAS DES QUESTIONS OUVERTES]
Si le corrigé contient plusieurs réponses possibles introduites par des expressions comme :
- "par exemple"
- "un autre exemple"
- "ou également"
- "on peut aussi"
- "autre solution"

alors toutes ces réponses représentent des VARIATIONS D’UNE MÊME RÉPONSE ATTENDUE.
Elles DOIVENT être fusionnées dans UN SEUL critère.

INTERDICTION ABSOLUE :
- Ne pas créer un critère par phrase
- Ne pas créer un critère par exemple
- Ne pas créer un critère par bullet point
- Ne pas découper les solutions alternatives

[RÈGLE DE REGROUPEMENT OBLIGATOIRE]
Si plusieurs formulations décrivent des solutions différentes mais correctes pour la même question ET ont le même nombre de points :
elles doivent être regroupées dans une seule chaîne "condition".

[SEULE EXCEPTION AUTORISÉE]
Créer plusieurs critères uniquement si :
- les points sont différents
- OU une séparation explicite de barème est indiquée dans le corrigé

[OBJECTIF]
Chaque "critère" doit représenter un bloc de notation cohérent, pas une liste d'exemples.

Retourner UNIQUEMENT un JSON valide conforme au schéma demandé.

Aucune explication.
Aucun commentaire.
Aucun texte avant ou après le JSON.

[RÈGLES DE FORMATAGE]
1. FORMULES MATHÉMATIQUES (LATEX) : 
   - Toute expression, variable ou équation mathématique DOIT être formatée en LaTeX.
   - Utilise le délimiteur `$` pour les équations en ligne et `$$` pour les équations en bloc.
   - RÈGLE D'ÉCHAPPEMENT JSON (CRITIQUE) : Tu dois OBLIGATOIREMENT doubler chaque antislash pour que le JSON soit valide. 
   - Exemple correct : "La variance est de $\\\\sigma^2 = \\\\frac{1}{N} \\\\sum_{i=1}^{N} (x_i - \\\\mu)^2$"
   - Exemple incorrect : "La variance est de $\sigma^2 = \frac{1}{N} \sum_{i=1}^{N} (x_i - \mu)^2$"
2. MATRICES ET VECTEURS :
   - Ne représente JAMAIS une matrice ou un vecteur avec de simples espaces ou sauts de ligne ASCII.
   - Tu DOIS utiliser les environnements LaTeX standard (`\\\\begin{bmatrix} ... \\\\end{bmatrix}` ou `\\\\begin{pmatrix} ... \\\\end{pmatrix}`).
   - Exemple correct : "$$ \\\\Sigma = \\\\begin{bmatrix} 1.0 & 0.9 \\\\ 0.9 & 1.0 \\\\end{bmatrix} $$"
3. GRAPHIQUES, FIGURES ET HISTOGRAMMES :
   - Si la correction attribue des points pour le tracé d'un graphique (ex: un histogramme ou une boîte à moustaches), n'essaie JAMAIS de le dessiner avec des caractères.
   - Tu DOIS extraire et lister textuellement les caractéristiques attendues du graphique pour obtenir les points.
   - Exemple correct : "Tracé de l'histogramme correct : présence de 5 bins de largeur 8, axes correctement nommés, et pics de fréquence sur les intervalles [18-26] et [42-50]."
4. TABLEAUX ET STRUCTURES EN GRILLE :
   - Les tableaux doivent être strictement formatés en Markdown.
   - RÈGLE DE SÉCURITÉ : Remplace les sauts de ligne à l'intérieur d'une même cellule par des espaces ou des virgules pour éviter de casser la structure de la ligne Markdown.

Les modificateurs structurels appliqués aux variables (comme le tilde, la barre supérieure ou le chapeau) DOIVENT être traduits par leurs commandes LaTeX spécifiques (ex: \\\\widetilde{}, \\\\overline{}).
Lors de l'analyse d'une équation enchaînée impliquant des opérations et des matrices (ex: A = B - C = Matrice), l'ensemble de l'expression DOIT être concaténé en une seule chaîne LaTeX continue.
RÈGLE D'ÉCHAPPEMENT MATRICIELLE (CRITIQUE) : Le saut de ligne LaTeX standard dans une matrice (\\) doit subir un double échappement pour rester valide dans la chaîne JSON, devenant ainsi \\\\\\\\.
    
    """

#     prompt += "\n[des examples de critères correctement formatés]\n"
#     prompt += """
# examples correctes
# """

    prompt += "\n[Des examples de critères incorrectement formatés que tu dois ne pas reproduire]\n"
    prompt += """

le correcteur propose :
1. Décrire précisément et brièvement une application qui peut utiliser ce jeu de données.
Plusieurs réponses sont possibles pour cette question. Par exemple, les autorités de gestion des routes peuvent
analyser les types d’accidents et leur gravité selon le type d’infrastucture routière et les conditions externes
(météo, présence d’obstacles) pour prendre des mesures correctives à titre préventif.
Un autre exemple c’est de développer une application SIG qui affiche les accidents sur une carte interactive (via
les variables Latitude/Longitude) et identifie les zones à forte concentration d’accidents. Ou également, aider les
autorités locales à prioriser des actions comme installation de radars, amélioration du revêtement, ajout de
signalisation … 1pt
example faux 
{
            "question_id": "Ex1_Q1",
            "context": "Le jeu de données « Road_Accidents» contient les informations sur les 30773 accidents de la route recensés en Grande Bretagne pour la période 2021-2022. Plus précisément, pour chaque accident repéré par un identifiant unique ID, voici une partie des descripteurs :\\\n• (Latitude, Longitude) : les deux coordonnées géographiques du lieu de l'accident,\\\n• Number of Casualties: le nombre de victimes,\\\n• Number_of_Vehicle : le nombre de véhicules impliqués,\\\n• Speed_limit: La vitesse maximale autorisée par la loi sur le lieu de l'accident (l'unité de mesure est le mile per hour ou mph),\\\n• Accident Severity : la sévérité de l'accident (mortel, sérieux, léger)\\\n• Road_Surface_Conditions : état de la surface de la route (sèche, humide, gelée, enneigée, inondée)\\\n• Carriageway_Hazard : présence ou absence d'obstacles dangereux sur la route (par exemple, animaux, objets tombés sur la route)",
            "question_text": "Décrire précisément et brièvement une application qui peut utiliser ce jeu de données.",
            "max_score": 1.0,
            "critère": [
                {
                    "condition": "Les autorités de gestion des routes peuvent analyser les types d'accidents et leur gravité selon le type d'infrastucture routière et les conditions externes (météo, présence d'obstacles) pour prendre des mesures correctives à titre préventif.",
                    "points": 1.0
                },
                {
                    "condition": "Développer une application SIG qui affiche les accidents sur une carte interactive (via les variables Latitude/Longitude) et identifie les zones à forte concentration d'accidents.",
                    "points": 1.0
                },
                {
                    "condition": "Aider les autorités locales à prioriser des actions comme installation de radars, amélioration du revêtement, ajout de signalisation ...",
                    "points": 1.0
                }
            ]
        }
ici le corrigé propose 3 réponses différentes pour la même question, tous sont juste et valent 1 point, mais ici le llm doit les regroupper en une critère unique valant 1 point, avec les 3 réponses concaténées dans la même chaîne "condition" car l'étudiant peut choisir n'importe laquelle de ces 3 réponses ou même les 3 pour obtenir le point.
    """
    prompt += "\n[DESCRIPTION DE TON RÔLE]\n"
    prompt += """
Tu es un assistant d’extraction de données strict.
Ton unique rôle est d’extraire et structurer fidèlement le contenu du corrigé PDF fourni.

Tu ne dois jamais reformuler, résumer, interpréter ni inventer de contenu.
Tu dois conserver strictement les formulations originales du document.
    """
    model_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ExamRubric,
        temperature=0.1
    )   

    active_model = FIRST_PRIMARY_MODEL
    try:
        print(f"Parsing rubric with {FIRST_PRIMARY_MODEL} (This may take 30-60 seconds)...")
        response = client.models.generate_content(
            model=FIRST_PRIMARY_MODEL,
            contents=[prompt, pdf_part], 
            config=model_config
        )
    except genai_errors.APIError as e:
        if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e):
            print(f"{FIRST_PRIMARY_MODEL} unavailable. Falling back to {FIRST_FALLBACK_MODEL}...")
            active_model = FIRST_FALLBACK_MODEL
            response = client.models.generate_content(
                model=FIRST_FALLBACK_MODEL,
                contents=[prompt, pdf_part],
                config=model_config
            )
        else:
            raise

    try:
        parsed_json = parse_json_response(response, active_model)
        parsed_json_safely = parse_json_response_safely(response, active_model)
        print(f"validate_question_ids: {validate_question_ids(ExamRubric.model_validate(parsed_json_safely))}")
        print(f"validate_score_sums: {validate_score_sums(ExamRubric.model_validate(parsed_json_safely))}")
        print(f"validate_criteria_points: {validate_criteria_points(ExamRubric.model_validate(parsed_json_safely))}")

        def generate_feedback():
            pass
        # feedback = generate_feedback(validate_question_ids(), validate_score_sums(), validate_duplicate_questions(), validate_empty_fields())
        # second_prompt = f"[MESSAGE DE FEEDBACK DE LA PREMIÈRE TENTATIVE]\n" + {feedback}
        # try : 
        #     print(f"Parsing rubric with {SECOND_PRIMARY_MODEL} (This may take 30-60 seconds)...")

        #     second_response = client.models.generate_content(
        #     model=SECOND_PRIMARY_MODEL,
        #     contents=[second_prompt, parsed_json],
        #     config=model_config
        #     )
        #     parsed_json = parse_json_response(second_response, SECOND_PRIMARY_MODEL)
        # except genai_errors.APIError as e:
        #     if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e):
        #         print(f"    {SECOND_PRIMARY_MODEL} unavailable. Falling back to {SECOND_FALLBACK_MODEL}...")
        #         active_model = SECOND_FALLBACK_MODEL
        #         second_response = client.models.generate_content(
        #             model=SECOND_FALLBACK_MODEL,
        #             contents=[second_prompt, parsed_json],
        #             config=model_config
        #         )
        #     else:
        #         raise

    except json.JSONDecodeError:
        print("❌ Error: Gemini did not return valid JSON. Here is the raw output:")
        print(response.text)
    
    #final step :
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(parsed_json, f, indent=4, ensure_ascii=False)

    with open(output_json_path_safely, 'w', encoding='utf-8') as f:
        json.dump(parsed_json_safely, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ Success! Structured rubric saved locally to {output_json_path}")
    print(f"Total questions parsed: {len(parsed_json)}")


#TODO later
# def parse_rubric_from_bytes(pdf_bytes, filename="rubric.pdf"):
    # """
    # Parses a rubric PDF from raw bytes and returns the structured JSON.
    # Uses the Gemini Files API for upload, then deletes after processing.
    
    # Args:
    #     pdf_bytes: Raw bytes of the rubric PDF.
    #     filename: Original filename (for logging).
        
    # Returns:
    #     list: Parsed rubric as a list of question dicts.
    # """
    # print(f"📋 Parsing rubric: {filename}...")

    # pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        
    # prompt = """
    # Tu es un assistant d'extraction de données strict. Ton SEUL rôle est de copier-coller et de structurer le texte exact du corrigé PDF fourni. 
    # TU NE DOIS JAMAIS reformuler, résumer, interpréter ou inventer des réponses modèles. Tu dois utiliser les mots exacts du document.

    # Pour CHAQUE question trouvée dans le document, extrais :
    # 1. "question_id" : L'identifiant de la question. 
    #    - RÈGLE ABSOLUE : L'identifiant DOIT inclure le numéro de l'exercice. Format obligatoire : "Ex[Numéro Exercice]_Q[Numéro/Lettre Question]". 
    #    - Exemples : "Ex1_Q1", "Ex1_Q3.a", "Ex2_Q1", "Ex3_QII.1".
    # 2. "context" : Le texte d'introduction global de l'exercice (description du dataset, liste des variables, etc.). 
    #    - RÈGLE ABSOLUE : Ce champ NE DOIT PAS être null si l'exercice possède une introduction. Tu DOIS copier et répéter l'introduction complète de l'exercice pour TOUTES les questions qui appartiennent à cet exercice.
    #    - RÈGLE POUR LES TABLEAUX : Si le contexte contient un tableau, tu DOIS obligatoirement le formater en Markdown (avec les symboles `|` et `-`).
    # 3. "question_text" : UNIQUEMENT la phrase de la question exacte qui a été posée à l'étudiant. 
    #    - RÈGLE POUR LES SOUS-QUESTIONS : Si c'est une sous-question (ex: 3.a, 3.b), tu DOIS concaténer le texte de la question parente avec le texte de la sous-question.
    # 4. "max_score" : Le score total de la question (float).
    # 5. "criteria" : Un tableau d'objets définissant le barème détaillé. 
    #    - RÈGLE ABSOLUE DE SÉPARATION : Tu DOIS obligatoirement séparer le texte de la condition et la valeur des points en DEUX clés distinctes : "condition" (string) et "points" (float).
    #    - RÈGLE POUR LES LISTES À PUCES ET BLOCS GLOBAUX : Si le corrigé indique un score global (ex: "1 pt") suivi de plusieurs tirets, puces, formules mathématiques ou explications SANS points spécifiques pour chaque ligne, tu DOIS regrouper TOUT ce texte en UNE SEULE "condition" valant ce score global. 
    #    - RÈGLE ANTI-INVENTION (CRITIQUE) : NE DIVISE JAMAIS les points toi-même. N'invente JAMAIS des scores comme 0.33, 0.34 ou 0.0. Si les points partiels ne sont pas explicitement écrits dans le texte, regroupe tout sous le score global.
    #    - RÈGLE D'EXHAUSTIVITÉ (SAUTS DE PAGE) : Une correction peut s'étaler sur plusieurs paragraphes ou traverser un saut de page. Tu DOIS capturer l'intégralité de la correction jusqu'à ce que tu rencontres la question suivante. Ne tronque pas la réponse.
    #    - Le texte des points (ex: "0.25 pt", "1 pt") NE DOIT JAMAIS être inclus dans la chaîne "condition".
    #    - ATTENTION AUX FUSIONS DE TEXTE : Si le texte dit "nbre d'occurrences 4 0.25 pt", la condition est "...nbre d'occurrences 4" et les points sont 0.25.
    #    - RÈGLE D'EXCLUSION : Ne crée un critère QUE s'il y a des points associés.

    # Voici la structure EXACTE requise pour les critères :
    # "criteria": [
    #     {
    #         "condition": "La largeur commune des bins est 50-10/N=8 => on aura 5 bins",
    #         "points": 0.25
    #     },
    #     {
    #         "condition": "[10 - 18[ (10, 13, 14, 15) => nbre d'occurrences 4",
    #         "points": 0.25
    #     }
    # ]
    # RENVOIE UNIQUEMENT UN TABLEAU JSON VALIDE.
    # IMPORTANT : dans toutes les chaînes JSON, échappe chaque antislash avec un double antislash. Exemple : écris "\\\\frac{{x}}{{y}}" et jamais "\\frac{{x}}{{y}}".
    # """
        
    # # Fixed: config must be a types.GenerateContentConfig object, not a dict
    # model_config = types.GenerateContentConfig(
    #     response_mime_type="application/json",
    #     temperature=0.1
    # )
    
    # active_model = FIRST_PRIMARY_MODEL
    # try:
    #     print(f"  Parsing with {FIRST_PRIMARY_MODEL}...")
    #     response = client.models.generate_content(
    #         model=FIRST_PRIMARY_MODEL,
    #         contents=[pdf_part, prompt], # Changed rubric_file to pdf_part
    #         config=model_config
    #     )
    #     parsed_json = parse_json_response(response, FIRST_PRIMARY_MODEL)
    # except Exception as e:
    #     print(f"  ⚠️ {FIRST_PRIMARY_MODEL} failed: {e}. Falling back to {FIRST_FALLBACK_MODEL}...")
    #     active_model = FIRST_FALLBACK_MODEL
    #     response = client.models.generate_content(
    #         model=FIRST_FALLBACK_MODEL,
    #         contents=[pdf_part, prompt], # Changed rubric_file to pdf_part
    #         config=model_config
    #     )
    #     parsed_json = parse_json_response(response, FIRST_FALLBACK_MODEL)

    # print(f"  ✅ Rubric parsed with {active_model}! {len(parsed_json)} questions found.")
    
    # return parsed_json




# --- EXECUTE ---
if __name__ == "__main__":
    PDF_INPUT_PATH = "/mnt/d/startup/experimenting_with_frontend/ai-service/exam_papers/Corrigé_ingénierie_données_2025.pdf"
    JSON_OUTPUT_PATH = "master_rubric.json"
    JSON_OUTPUT_PATH_SAFELY = "safe_rubric.json"
    
    if not os.path.exists("exam_papers"):
        print("Creating 'exam_papers' folder. Please place your PDF inside it and run again.")
        os.makedirs("exam_papers")
    elif not os.path.exists(PDF_INPUT_PATH):
        print(f"File not found: {PDF_INPUT_PATH}. Please make sure the PDF is in the correct folder.")
    else:
        parse_rubric_pdf(PDF_INPUT_PATH, JSON_OUTPUT_PATH, JSON_OUTPUT_PATH_SAFELY)
