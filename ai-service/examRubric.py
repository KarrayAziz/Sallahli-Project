from pydantic import BaseModel

class Criterion(BaseModel):
    condition: str
    points: float

class Question(BaseModel):
    question_id: str
    context: str
    question_text: str
    max_score: float
    criteria: list[Criterion]

class ExamRubric(BaseModel):
    questions: list[Question]