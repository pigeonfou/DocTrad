"""Fail closed when a model damages technical placeholders."""
import re
import secrets
from collections import Counter

TECH = re.compile(r"(?<!\w)(?:ISO\s+\d+|[+-]?\d+(?:[.,]\d+)?\s*(?:VDC|VAC|mA|kV|kW|MHz|GHz|Nm|mm|cm|kg|°C|V|A|W|Hz|%)(?!\w)|[A-Z]+[A-Z0-9]*(?:[-][A-Z0-9]+)+|[A-Za-z]+\d+[A-Za-z0-9]*|[A-Z]{2,}|RoHS|REACH)(?!\w)")
NUMBERS = re.compile(r"(?<![\w])[+-]?\d+(?:[.,]\d+)?")

def protect(text, glossary=None):
    mapping = {}
    nonce = secrets.token_hex(4)
    def save(value):
        token = f"ZXQ{nonce}Q{len(mapping)}QXZ"
        mapping[token] = value
        return token
    # One combined pass prevents matching inside generated tokens.
    entries = glossary or {}
    terms = sorted(entries, key=len, reverse=True)
    alternatives = [r"(?<!\w)" + re.escape(t) + r"(?!\w)" for t in terms]
    pattern = re.compile("|".join(alternatives + [TECH.pattern, NUMBERS.pattern]))
    def replace(match):
        value = match.group()
        return save(entries.get(value, value))
    return pattern.sub(replace, text), mapping

def restore(text, mapping):
    for token, value in mapping.items():
        if text.count(token) != 1:
            raise ValueError("Le modèle a modifié une donnée protégée ; segment à vérifier.")
        text = text.replace(token, value)
    return text

def check(source, target):
    warnings = []
    if Counter(NUMBERS.findall(source)) != Counter(NUMBERS.findall(target)):
        warnings.append("Nombre ajouté, absent ou modifié")
    if Counter(TECH.findall(source)) != Counter(TECH.findall(target)):
        warnings.append("Référence ou unité technique modifiée")
    return warnings

def segment(text, max_chars=1000):
    chunks = []
    for paragraph in text.splitlines():
        if not paragraph.strip(): continue
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", paragraph)
        current = ""
        for sentence in sentences:
            if len(sentence) > max_chars:
                if current: chunks.append(current); current = ""
                # Never split a technical reference: split only at whitespace.
                words = sentence.split()
                for word in words:
                    if len(current) + len(word) + 1 > max_chars and current:
                        chunks.append(current); current = ""
                    current = (current + " " + word).strip()
            elif len(current) + len(sentence) + 1 > max_chars and current:
                chunks.append(current); current = sentence
            else: current = (current + " " + sentence).strip()
        if current: chunks.append(current)
    return chunks
