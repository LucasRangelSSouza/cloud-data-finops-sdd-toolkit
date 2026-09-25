"""Deterministic PPTX generation from structured findings."""

from .deck import SECTIONS, build_presentation, render_deck, slide_outline, write_deck

__all__ = ["SECTIONS", "build_presentation", "render_deck", "slide_outline", "write_deck"]
