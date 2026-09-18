from __future__ import annotations

from app.database.models import Question

_DIFFICULTY_LABEL = {1: "Basic", 2: "Intermediate", 3: "Advanced", 4: "Internals", 5: "Interview Trap"}


def format_question_message(question: Question, attempt_number: int | None = None) -> str:
    topic = question.concept.topic.name if question.concept and question.concept.topic else ""
    concept = question.concept.name if question.concept else ""
    level = _DIFFICULTY_LABEL.get(question.difficulty, str(question.difficulty))

    lines = [
        f"*{topic} — {concept}*",
        f"_{level} · {question.qtype.replace('_', ' ')}_",
        "",
        question.body,
    ]
    if question.code_snippet:
        lines += ["", f"```python\n{question.code_snippet}\n```"]
    lines += ["", "Reply to this message with your answer."]
    return "\n".join(lines)
