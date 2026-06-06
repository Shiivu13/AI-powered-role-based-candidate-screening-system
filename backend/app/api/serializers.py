from app.models.db_models import Question
from app.models.schemas import QuestionOut, RetrievalMeta


def question_to_out(q: Question, include_answer: bool = True) -> QuestionOut:
    answer = q.answer if include_answer else None
    return QuestionOut(
        id=q.id,
        question_number=q.question_number,
        question_text=q.question_text,
        question_type=q.question_type,
        difficulty=q.difficulty,
        topic=q.topic,
        retrieval_meta=RetrievalMeta(**q.retrieval_meta) if q.retrieval_meta else None,
        created_at=q.created_at,
        answer_text=answer.answer_text if answer else None,
        score=answer.score if answer else None,
        feedback=answer.feedback if answer else None,
        eval_detail=answer.eval_detail if answer else None,
    )
