from __future__ import annotations

import random
import re
import secrets
from collections import Counter, defaultdict

from .models import CandidateQuestions, Question


LABEL_PATTERNS = (
    re.compile(r"\b(options?|opciones?)\s+([A-F])\b", re.IGNORECASE),
    re.compile(r"(选项|選択肢)\s*([A-F])", re.IGNORECASE),
    re.compile(r"([（(])([A-F])([）)])"),
)


def _remap_explanation_labels(text: str, mapping: dict[str, str]) -> str:
    value = text
    for pattern_index, pattern in enumerate(LABEL_PATTERNS):
        def replace(match: re.Match[str]) -> str:
            groups = list(match.groups())
            label_index = next(
                index for index, group in enumerate(groups)
                if group.upper() in mapping
            )
            groups[label_index] = mapping[groups[label_index].upper()]
            if pattern_index == 0:
                return f"{groups[0]} {groups[1]}"
            if pattern_index == 1:
                return f"{groups[0]}{groups[1]}"
            return "".join(groups)

        value = pattern.sub(replace, value)
    return value


def shuffle_answer_options(
    candidate: CandidateQuestions,
    *,
    rng: random.Random | None = None,
) -> tuple[CandidateQuestions, dict[str, int]]:
    randomizer = rng or secrets.SystemRandom()
    grouped: defaultdict[int, list[Question]] = defaultdict(list)
    for question in candidate.questions:
        if question.options and question.correct_option_id is not None:
            grouped[len(question.options)].append(question)

    target_positions: dict[str, int] = {}
    for option_count, questions in grouped.items():
        positions: list[int] = []
        while len(positions) < len(questions):
            cycle = list(range(option_count))
            randomizer.shuffle(cycle)
            positions.extend(cycle)
        target_positions.update(
            (question.id, position)
            for question, position in zip(questions, positions[: len(questions)], strict=True)
        )

    shuffled_questions: list[Question] = []
    correct_distribution: Counter[str] = Counter()
    for question in candidate.questions:
        if not question.options or question.correct_option_id is None:
            shuffled_questions.append(question)
            continue

        correct = next(
            option for option in question.options if option.id == question.correct_option_id
        )
        distractors = [option for option in question.options if option is not correct]
        randomizer.shuffle(distractors)
        target_position = target_positions[question.id]
        ordered = distractors.copy()
        ordered.insert(target_position, correct)

        old_to_new: dict[str, str] = {}
        options: list[dict[str, str]] = []
        for index, option in enumerate(ordered):
            option_id = chr(ord("A") + index)
            old_to_new[option.id] = option_id
            options.append({"id": option_id, "text": option.text})
        correct_option_id = old_to_new[question.correct_option_id]
        correct_distribution[correct_option_id] += 1

        data = question.model_dump()
        data.update(
            {
                "options": options,
                "correct_option_id": correct_option_id,
                "explanation": _remap_explanation_labels(
                    question.explanation, old_to_new
                ),
            }
        )
        shuffled_questions.append(Question.model_validate(data))

    return (
        CandidateQuestions(questions=shuffled_questions),
        dict(sorted(correct_distribution.items())),
    )
