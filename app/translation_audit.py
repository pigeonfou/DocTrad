"""Deterministic offline QA for English-to-French technical documents."""
import re
from .terminology import PROTECTED_NAMES

BAD_FR = {
    "houblon spatial": "« Spatial Hops » signifie « sauts spatiaux »",
    "radio ombre": "Nom commercial Shadow Radio probablement traduit",
    "radio fantôme": "Nom commercial Ghost Radio probablement traduit",
    "1 deuxième": "Confusion entre second (durée) et deuxième (rang)",
    "noeuds avec": "Vérifier la fluidité de la phrase technique",
}

def audit_translation(source, target):
    """Return actionable warnings without silently rewriting technical content."""
    warnings = []
    folded = target.casefold()
    for wrong, reason in BAD_FR.items():
        if wrong in folded:
            warnings.append("Terminologie suspecte : " + reason)
    for name in PROTECTED_NAMES:
        if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", source, re.I):
            if not re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", target, re.I):
                warnings.append("Désignation absente ou modifiée : " + name)
    for token in re.findall(r"(?<![\w])(?:AN/PRC-\d+[A-Z]?|TW-\d+|ORION\s+X\d+)(?!\w)", source):
        if token not in target:
            warnings.append("Référence produit perdue : " + token)
    if source.strip() and not target.strip():
        warnings.append("Traduction vide")
    return list(dict.fromkeys(warnings))
