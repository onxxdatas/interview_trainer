from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class EvaluationResult(BaseModel):
    correctness: str = Field(description="one of: correct, mostly_correct, partially_correct, incorrect, no_answer")
    score: int = Field(ge=0, le=10)
    strengths: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)
    incorrect_claims: list[str] = Field(default_factory=list)
    feedback: str
    follow_up_question: str | None = None
    concepts_to_review: list[str] = Field(default_factory=list)

    @field_validator("correctness")
    @classmethod
    def _valid_correctness(cls, v: str) -> str:
        allowed = {"correct", "mostly_correct", "partially_correct", "incorrect", "no_answer"}
        if v not in allowed:
            raise ValueError(f"correctness must be one of {allowed}, got {v!r}")
        return v


class GeneratedQuestion(BaseModel):
    body: str
    code_snippet: str | None = None
    qtype: str
    expected_points: list[str] = Field(default_factory=list)


class InterviewAssessment(BaseModel):
    technical_strengths: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    repeatedly_missed_concepts: list[str] = Field(default_factory=list)
    communication_clarity: str
    code_reasoning_ability: str
    observations: str
