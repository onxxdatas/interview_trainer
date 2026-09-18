from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Next Question", callback_data="next_question")],
            [
                InlineKeyboardButton(text="⏸ Pause", callback_data="pause"),
                InlineKeyboardButton(text="▶️ Resume", callback_data="resume"),
            ],
            [
                InlineKeyboardButton(text="📊 My Stats", callback_data="stats"),
                InlineKeyboardButton(text="🩹 Weak Topics", callback_data="weak"),
            ],
            [InlineKeyboardButton(text="🎤 Start Interview", callback_data="start_interview")],
        ]
    )


def interview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🛑 End Interview", callback_data="end_interview")]]
    )
