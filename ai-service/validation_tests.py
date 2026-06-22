from examRubric import ExamRubric
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
def validate_score_sums(exam_rubric: ExamRubric):
    """
    Validate that the sum lf all the questions is 20
    """
    sum_points = 0
    total_points = 20

    for question in exam_rubric.questions:
        sum_points += question.max_score

    is_valid = sum_points == total_points

    return {
        "valid": is_valid,
        "errors": [] if is_valid else sum_points
    }
def validate_criteria_points(exam_rubric: ExamRubric, tolerance: float = 1e-6):
    """
    Validates that each question's criteria points sum up to its max_score.
    """

    errors = []
    is_valid = True

    for question in exam_rubric.questions:
        total_criteria_points = sum(float(c.points) for c in question.criteria)

        expected = question.max_score or 0.0

        if abs(total_criteria_points - expected) > tolerance:
            is_valid = False
            errors.append({
                "question_id": question.question_id,  # safer if your model uses id_question
                "expected_max_score": expected,
                "sum_criteria_points": total_criteria_points,
                "difference": round(total_criteria_points - expected, 6)
            })

    return {
        "valid": is_valid,
        "errors": errors
    }

# validate_duplicate_questions()
# def validate_empty_fields