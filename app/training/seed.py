from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Question
from app.database.repositories import get_or_create_concept, get_or_create_topic
from app.training.question_bank import SEED_DATA


async def seed_question_bank(session: AsyncSession) -> None:
    for topic_slug, topic_data in SEED_DATA.items():
        topic = await get_or_create_topic(session, topic_data["name"], topic_slug)
        for concept_slug, concept_data in topic_data["concepts"].items():
            concept = await get_or_create_concept(session, topic, concept_data["name"], concept_slug)
            for q in concept_data["questions"]:
                exists = await session.execute(
                    select(Question).where(
                        Question.concept_id == concept.id, Question.body == q["body"]
                    )
                )
                if exists.scalar_one_or_none():
                    continue
                session.add(
                    Question(
                        concept_id=concept.id,
                        difficulty=q["difficulty"],
                        qtype=q["qtype"],
                        body=q["body"],
                        code_snippet=q.get("code_snippet"),
                        expected_points=q.get("expected_points", []),
                        hints=q.get("hints", []),
                        source="curated",
                    )
                )
    await session.commit()
