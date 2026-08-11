"""Canonical, derived course identifiers used by auth and instructor UI."""

from __future__ import annotations


def normalize_course_component(value: str) -> str:
    return value.strip().upper()


def course_identifier(course_code: str, semester: str) -> str:
    return f"{normalize_course_component(course_code)}-{normalize_course_component(semester)}"


def normalize_course_identifier(value: str) -> str:
    return value.strip().upper()
