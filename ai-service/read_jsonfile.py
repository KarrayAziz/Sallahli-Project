import json 
from examRubric import ExamRubric



with open('/mnt/d/startup/experimenting_with_frontend/ai-service/master_rubric.json', 'r') as f:   
    data = json.load(f)




import re

def validate_question_ids(exam_rubric: ExamRubric):
    """
    Validates that all question IDs follow the required format:
    Ex[Number]_Q[Number/Letter(.subpart)]

    Example valid:
        Ex1_Q1
        Ex2_Q3.a
        Ex3_QII.1
    """

    pattern = re.compile(r"^Ex\d+_Q[\w.]+$")

    errors = []
    is_valid = True

    for i, question in enumerate(exam_rubric.questions):
        # adapt to your real field name safely
        question_id = getattr(question, "question_id", None)



        if question_id is None:
            is_valid = False
            errors.append({
                "index": i,
                "error": "Missing question ID field"
            })
            continue

        if not pattern.match(question_id):
            is_valid = False
            errors.append({
                "question_id": question_id,
                "error": "Invalid format",
                "expected_format": "Ex<number>_Q<id>"
            })

    return {
        "valid": is_valid,
        "errors": errors
    }
rubric = ExamRubric.model_validate(data)

print(validate_question_ids(rubric))