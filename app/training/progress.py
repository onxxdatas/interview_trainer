from __future__ import annotations

from app.database.models import ReviewSchedule


def format_stats_message(stats: dict) -> str:
    lines = [
        "*Training stats*",
        "",
        f"Training time: {stats['training_hours']} h",
        f"Questions: {stats['questions']}",
        f"Answered: {stats['answered']}",
        f"Overdue: {stats['overdue']}",
    ]
    avg = stats["average_score"]
    lines.append(f"Average score: {avg}/10" if avg is not None else "Average score: n/a yet")

    if stats["strong"]:
        lines.append("")
        lines.append("Strong areas:")
        for s in stats["strong"]:
            lines.append(f"• {s.concept.name} — mastery {round(s.mastery * 100)}%")

    if stats["weak"]:
        lines.append("")
        lines.append("Needs review:")
        for s in stats["weak"]:
            lines.append(f"• {s.concept.name} — mastery {round(s.mastery * 100)}%")

    if stats["recent_mistakes"]:
        lines.append("")
        lines.append("Recent mistakes:")
        for m in stats["recent_mistakes"]:
            lines.append(f"• {m}")

    return "\n".join(lines)


def format_topics_message(schedules: list[ReviewSchedule]) -> str:
    if not schedules:
        return "No topics tracked yet — answer a few questions first."
    by_topic: dict[str, list[ReviewSchedule]] = {}
    for s in schedules:
        topic_name = s.concept.topic.name if s.concept.topic else "Other"
        by_topic.setdefault(topic_name, []).append(s)

    lines = ["*Topics and concept mastery*", ""]
    for topic_name, items in by_topic.items():
        lines.append(f"*{topic_name}*")
        for s in sorted(items, key=lambda x: x.mastery):
            pct = round(s.mastery * 100)
            due = "due now" if s.attempts == 0 else ""
            lines.append(f"  {s.concept.name}: {pct}% {due}".rstrip())
        lines.append("")
    return "\n".join(lines).strip()


def format_weak_message(schedules: list[ReviewSchedule], limit: int = 5) -> str:
    attempted = [s for s in schedules if s.attempts > 0]
    if not attempted:
        return "Not enough data yet — answer a few questions first."
    weakest = sorted(attempted, key=lambda s: s.mastery)[:limit]
    lines = ["*Weakest concepts right now*", ""]
    for s in weakest:
        lines.append(f"• {s.concept.name} — mastery {round(s.mastery * 100)}%, {s.correct}/{s.attempts} correct")
    return "\n".join(lines)
