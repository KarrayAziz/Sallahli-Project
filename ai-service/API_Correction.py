import json
import os
import time
from google import genai
from google.genai import types
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 1. CONFIGURATION DES CHEMINS ---
# On utilise un chemin local. Pointant par exemple vers un dossier "data" 
# situé dans le même répertoire que ce script Python.
BASE_DIR = './data' # Assure-toi de créer ce dossier et d'y mettre tes JSON !

RUBRIC_PATH = os.path.join(BASE_DIR, 'master_rubric.json')
STUDENT_ANSWERS_PATH = os.path.join(BASE_DIR, 'student_answers.json')
OUTPUT_GRADES_PATH = os.path.join(BASE_DIR, 'graded_results_gemini.json')

# --- 2. CHARGEMENT DES DONNÉES ---
# Moved to __main__ block to prevent crash on import



# --- 3. CONFIGURATION DE L'API VERTEX AI ---
print("🔑 Authentification Google Cloud...")

# Les informations de ton projet (inchangées)
PROJECT_ID = "gen-lang-client-0125580043"
LOCATION = "global"

print(f"⚙️ Initialisation de Vertex AI pour le projet {PROJECT_ID}...")

# Le SDK unifié va automatiquement chercher tes identifiants locaux (ADC)
# Plus besoin de popup !
client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION
)

# On garde le modèle que tu as défini
MODEL_ID = 'gemini-3.1-flash-lite-preview'

print("✅ Modèle Vertex AI connecté avec succès !")


# --- 4. FONCTION D'ÉVALUATION (PROMPT EXPERT) ---

def grade_question_gemini(student_answer, rubric_item):
    """
    Évalue une question spécifique en utilisant Gemini et retourne un JSON.
    """
    q_id = rubric_item.get("question_id")
    q_text = rubric_item.get("question_text", "")
    max_score = rubric_item.get("max_score", 0)
    criteria = rubric_item.get("criteria", [])

    context_text = rubric_item.get("context", "")
    context_str = f"CONTEXTE : {context_text}\n" if context_text else ""

    prompt = f"""Agis comme un professeur d'université et correcteur d'examen expert en ingénierie des données et statistiques. Je vais te fournir un corrigé avec un barème détaillé, puis la copie d'un étudiant pour une question précise.
Tu dois évaluer la réponse de l'étudiant en appliquant rigoureusement les règles de correction suivantes :

1. Découpage intelligent du barème : Si le barème global d'une question contient plusieurs idées implicites ou explicites, tu dois le subdiviser en sous-critères fractionnés (ex: une idée valant 0.5 pt peut être divisée en deux attentes à 0.25 pt).
2. Gestion des justifications non demandées : Si la question ou le barème n'attribue pas de points spécifiques à une justification, accorde la totalité des points dès lors que la réponse directe de l'étudiant est correcte.
3. Flexibilité et pertinence métier : Ne sois pas prisonnier des mots exacts du corrigé. Si l'étudiant utilise un concept équivalent ou donne une justification scientifiquement correcte en ingénierie des données, tu dois lui accorder les points correspondants.
4. Idée générale vs Précision mécanique :
   - Accorde des points partiels (ex: la moitié) si l'étudiant évoque la bonne idée générale ou le bon mécanisme de base.
   - Pénalise l'imprécision (ex: retire 0.25 pt) si l'étudiant a compris l'idée globale mais omet d'expliquer pourquoi ou comment le mécanisme fonctionne.
5. Zéro point pour la paraphrase : N'accorde AUCUN point à un étudiant qui se contente de reformuler la question ou de constater un fait sans fournir d'explication sous-jacente.
6. Analyse explicite des graphiques : Avant de noter une figure, tu dois d'abord écrire une phrase décrivant précisément ce que l'étudiant a tracé et le comparer factuellement aux attentes du corrigé.
7. Format de réponse : Liste les sous-critères du barème et indique "Validé", "Partiellement validé" ou "Non validé". Justifie brièvement ta décision.

--- CONTRAINTE DE FORMATAGE TECHNIQUE OBLIGATOIRE ---
Pour que mon système Python fonctionne, tu dois renvoyer ton évaluation UNIQUEMENT sous forme de JSON valide.
Le JSON DOIT avoir cette structure exacte :
{{
    "raisonnement": "Ton application de la Règle 6 (si graphique) puis ta liste des sous-critères avec mention Validé/Partiellement validé/Non validé et tes justifications détaillées.",
    "score_final": 0.5,
    "justification": "Une seule phrase résumant la note globale pour l'étudiant."
}}

--- DONNÉES DE LA QUESTION ({q_id}) ---
{context_str}
QUESTION : {q_text}
SCORE MAXIMUM : {max_score}
BARÈME : {json.dumps(criteria, ensure_ascii=False)}

RÉPONSE DE L'ÉTUDIANT : "{student_answer}"
"""

    # Appel à l'API Gemini via le SDK unifié Vertex AI
    response = client.models.generate_content(
        model=MODEL_ID, 
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )

    return response.text

# --- API-friendly function (for FastAPI server) ---
def grade_exam(master_rubric, student_answers, progress_callback=None):
    """
    Grades a full exam given a rubric and student answers.
    
    Args:
        master_rubric: List of rubric question dicts.
        student_answers: Dict mapping question_id -> student answer text.
        progress_callback: Optional callable(question_id, score, max_score, index, total)
            for real-time progress reporting.
        
    Returns:
        dict: Full grading results including per-question evaluations and BILAN_GLOBAL.
    """
    final_grades = {}
    note_globale = 0.0
    total_questions = len(master_rubric)
    
    print(f"\n🚀 STARTING AI GRADING ({total_questions} questions)")
    print("-" * 50)

    def grade_single(args):
        i, rubric_item = args
        q_id = rubric_item.get("question_id")
        max_score = rubric_item.get("max_score", 0)

        if q_id not in student_answers:
            return i, q_id, None

        student_ans = student_answers[q_id]
        print(f"📡 Grading question {q_id} ({i+1}/{total_questions})...")

        try:
            grade_result_str = grade_question_gemini(student_ans, rubric_item)
            evaluation = json.loads(grade_result_str)

            try:
                score_obtenu = float(evaluation.get("score_final", 0.0))
            except (ValueError, TypeError):
                score_obtenu = 0.0

            print(f"   ✅ {q_id} graded! Score: {score_obtenu} / {max_score}")
            return i, q_id, {
                "student_answer": student_ans,
                "ai_evaluation": evaluation,
                "max_score": max_score,
                "score": score_obtenu
            }

        except Exception as e:
            print(f"   ❌ Error grading {q_id}: {e}")
            return i, q_id, {
                "student_answer": student_ans,
                "ai_evaluation": {
                    "raisonnement": f"Erreur lors de la correction: {str(e)}",
                    "score_final": 0.0,
                    "justification": "Une erreur technique est survenue."
                },
                "max_score": max_score,
                "score": 0.0,
                "erreur": str(e)
            }

    with ThreadPoolExecutor(max_workers=min(total_questions, 5)) as executor:
        futures = {executor.submit(grade_single, (i, item)): i for i, item in enumerate(master_rubric)}
        for future in as_completed(futures):
            i, q_id, result = future.result()
            if result is None:
                continue
            score_obtenu = result.pop("score")
            note_globale += score_obtenu
            final_grades[q_id] = result
            if progress_callback:
                progress_callback(q_id, score_obtenu, result["max_score"], i + 1, total_questions)

    # Calculate the total max possible score
    total_max = sum(item.get("max_score", 0) for item in master_rubric)
    # Scale to /20 if needed
    if total_max > 0 and total_max != 20:
        note_sur_20 = round((note_globale / total_max) * 20, 2)
    else:
        note_sur_20 = round(note_globale, 2)

    final_grades["BILAN_GLOBAL"] = {
        "total_points": round(note_globale, 2),
        "total_max": round(total_max, 2),
        "note_sur_20": f"{note_sur_20}/20",
        "message": "Somme automatique de tous les scores partiels calculés par l'IA.",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    print("-" * 50)
    print(f"🎓 FINAL SCORE: {round(note_globale, 2)} / {round(total_max, 2)} ({note_sur_20}/20)")

    return final_grades


# --- 5. EXÉCUTION DE LA CORRECTION ---

if __name__ == "__main__":
    print("📁 Chargement des fichiers locaux...")

    try:
        with open(RUBRIC_PATH, 'r', encoding='utf-8') as f:
            master_rubric = json.load(f)
        print(f"✅ Rubric loaded successfully! ({len(master_rubric)} questions)")

        with open(STUDENT_ANSWERS_PATH, 'r', encoding='utf-8') as f:
            student_answers = json.load(f)
        print(f"✅ Student Answers loaded successfully! ({len(student_answers)} answers)")

    except FileNotFoundError as e:
        print(f"❌ ERREUR : Fichier introuvable. Fichier manquant : {e.filename}")
        exit(1)

    final_grades = {}
    note_globale = 0.0
    
    print(f"\n🚀 DÉMARRAGE DE LA CORRECTION AUTOMATIQUE ({len(master_rubric)} questions)")
    print("-" * 50)
    start_time = time.time()
    
    for rubric_item in master_rubric:
        q_id = rubric_item.get("question_id")
        max_score = rubric_item.get("max_score", 0)
        
        if q_id in student_answers:
            print(f"📡 Évaluation de la question {q_id}...")
            student_ans = student_answers[q_id]
            
            try:
                # 1. Appel API pour la question spécifique
                grade_result_str = grade_question_gemini(student_ans, rubric_item)
                evaluation = json.loads(grade_result_str)
                
                # 2. Sécurisation et extraction du score
                try:
                    score_obtenu = float(evaluation.get("score_final", 0.0))
                except (ValueError, TypeError):
                    score_obtenu = 0.0 
                    
                # 3. Ajout au cumulatif de la note
                note_globale += score_obtenu
                
                # 4. Enregistrement dans le dictionnaire
                final_grades[q_id] = {
                    "student_answer": student_ans,
                    "ai_evaluation": evaluation
                }
                
                print(f"   ✅ {q_id} corrigé ! Note : {score_obtenu} / {max_score}")
    
                # Pause pour respecter les quotas Vertex AI
                time.sleep(1)
    
            except Exception as e:
                print(f"   ❌ Erreur lors de la correction de {q_id} : {e}")
                final_grades[q_id] = {"erreur": str(e)}
    
    # --- 6. BILAN ET SAUVEGARDE ---
    
    # Calcul final sur 20 (ajustable si le total max n'est pas 20)
    final_grades["BILAN_GLOBAL"] = {
        "total_points": round(note_globale, 2),
        "note_sur_20": f"{round(note_globale, 2)}/20",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    end_time = time.time()
    
    # Sauvegarde locale (dans le dossier data configuré en section 1)
    try:
        with open(OUTPUT_GRADES_PATH, 'w', encoding='utf-8') as f:
            json.dump(final_grades, f, indent=4, ensure_ascii=False)
        
        print("-" * 50)
        print(f"\n🎉 Correction terminée en {round(end_time - start_time, 2)} secondes !")
        print(f"🎓 NOTE FINALE DE L'ÉTUDIANT : {round(note_globale, 2)} / 20")
        print(f"📁 Résultats sauvegardés dans : {OUTPUT_GRADES_PATH}")

    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde du fichier : {e}")