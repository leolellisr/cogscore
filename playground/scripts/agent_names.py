"""Presentation-only Cognitive Strategy labels used in the thesis.

Never rewrite raw agent IDs, training stages, CSV metrics, or database keys.
"""
from __future__ import annotations

import re

ALIASES = {
    **{f"Substage{i}": f"CS{i}" for i in range(1, 6)},
    **{f"Substage{i}_DQN": f"CS{i}" for i in range(1, 6)},
    "Substage1_QL": "CS6", "1st_ql": "CS6",
    "Substage2_QL": "CS7", "2nd_ql": "CS7",
    "Substage3_QL": "CS8", "3rd_ql": "CS8",
    "Substage1_QL_Noise": "CS6_nEC", "1st_ql_noise": "CS6_nEC",
    "Substage1_Theoretic": "CS1_T", "Substage3_Theoretic": "CS3_T",
}
# Prevent partial matches (e.g. Substage1 inside Substage1_QL_Noise).
_PATTERN = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(
    re.escape(k) for k in sorted(ALIASES, key=len, reverse=True)
) + r")(?![A-Za-z0-9_])", re.IGNORECASE)
_LOOKUP = {k.lower(): v for k, v in ALIASES.items()}

def display_agent(name: str) -> str:
    """Translate agent aliases without touching values or metric columns."""
    return _PATTERN.sub(lambda m: _LOOKUP[m.group(0).lower()], str(name))

def relabel_figure(fig) -> None:
    """Relabel already-computed matplotlib graphics; numerical artists unchanged."""
    for ax in fig.axes:
        legend = ax.get_legend()
        if legend is not None:
            for item in legend.get_texts():
                item.set_text(display_agent(item.get_text()))
        for text in (ax.title, ax.xaxis.label, ax.yaxis.label):
            text.set_text(display_agent(text.get_text()))
        for text in ax.texts:
            text.set_text(display_agent(text.get_text()))
    for text in fig.texts:
        text.set_text(display_agent(text.get_text()))
