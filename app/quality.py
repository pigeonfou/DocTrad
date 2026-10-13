"""Fail closed when a model damages technical placeholders."""
import re
import secrets
from collections import Counter

TECH = re.compile(r"(?<!\w)(?:ISO\s+\d+|[+-]?\d+(?:[.,]\d+)?\s*(?:dBm|dBc|dB|kHz|mW|VDC|VAC|mA|kV|kW|MHz|GHz|Nm|mm|cm|kg|°C|V|A|W|Hz|%)(?!\w)|[A-Z]+[A-Z0-9]*(?:[-][A-Z0-9]+)+|[A-Za-z]+\d+[A-Za-z0-9]*|[A-Z]{2,}s?|RoHS|REACH)(?!\w)")
NUMBERS = re.compile(r"(?<![\w])[+-]?\d+(?:[.,]\d+)?")


def split_sentences(text):
    """Keep dotted abbreviations inside the complete technical sentence."""
    output=[];start=0
    for boundary in re.finditer(r'(?<=[.!?])\s+(?=[A-Z])',text):
        prefix=text[:boundary.start()]
        if re.search(r'(?:\b[A-Z](?:\.[A-Z])+\.|\b(?:Mr|Ms|Dr|Prof|Inc|Ltd)\.)$',prefix,re.I):
            continue
        output.append(text[start:boundary.start()]);start=boundary.end()
    output.append(text[start:])
    return output

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

def measurement_qa_text(text):
    """A modulation prefix followed by dBm is a measurement, not a part number."""
    text = text.replace('−', '-')
    return re.sub(r'\b(FM|AM)\s*[-–]\s*(?=\d+(?:[.,]\d+)?\s*dBm\b)', r'\1 : -', text)

def check(source, target):
    source, target = measurement_qa_text(source), measurement_qa_text(target)
    warnings = []
    # French decimal commas represent the same technical value.
    def canonical(values):
        return Counter(re.sub(r"\s+", "", re.sub(r"(?<=\d),(?=\d)", ".", value)) for value in values)
    if canonical(NUMBERS.findall(source)) != canonical(NUMBERS.findall(target)):
        warnings.append("Nombre ajouté, absent ou modifié")
    comparisons = r'[<>≤≥]\s*[+-]?\d+(?:[.,]\d+)?'
    if canonical(re.findall(comparisons, source)) != canonical(re.findall(comparisons, target)):
        warnings.append("Comparaison chiffrée absente ou modifiée")
    from .terminology import DEFAULT_TERMS
    from .terminology import structured_technical_text
    exact_heading = (DEFAULT_TERMS.get(source.strip()) == target.strip()
                     or structured_technical_text(source) == target.strip())
    def references(text):
        return [value[:-1] if re.fullmatch(r'[A-Z]{2,}s', value) else value for value in TECH.findall(text)]
    if not exact_heading and canonical(references(source)) != canonical(references(target)):
        warnings.append("Référence ou unité technique modifiée")
    return warnings

def segment(text, max_chars=1000):
    chunks = []
    for paragraph in text.splitlines():
        if not paragraph.strip(): continue
        sentences = split_sentences(paragraph)
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



def inference_defects(source, target):
    """Reject unmistakable generation drift without guessing at its meaning."""
    defects = []
    foreign = r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]'
    if re.search(foreign, target) and not re.search(foreign, source):
        defects.append('foreign_script')
    for identifier in ('SAASM', 'ISR', 'TOP SECRET'):
        pattern = r'(?<!\w)' + re.escape(identifier) + r'(?!\w)'
        if re.search(pattern, target) and not re.search(pattern, source):
            defects.append('invented_identifier')
            break
    import json
    from .terminology import required_names
    body, separator, last = target.rstrip().rpartition('\n')
    if separator and body.strip():
        try:
            echoed = json.loads(last)
        except (ValueError, TypeError):
            echoed = None
        names = set(required_names(source).values())
        if (isinstance(echoed, list) and echoed and all(isinstance(item,str) for item in echoed)
                and set(echoed) <= names and last not in source):
            defects.append('prompt_echo')
    if strip_identifier_echo(source, target, list(required_names(source).values())) != target and 'prompt_echo' not in defects:
        defects.append('prompt_echo')
    return defects


def strip_identifier_echo(source, target, names):
    """Remove source-scoped instruction echoes, never a source list or new facts."""
    import json
    body, separator, last = target.rstrip().rpartition('\n')
    if not separator or not body.strip() or not names or '[' in source or ']' in source:
        return target
    try:
        echoed = json.loads(last)
    except (ValueError, TypeError):
        echoed = None
    if echoed == names:
        return body.rstrip()
    remaining = last
    matched = []
    for name in sorted(set(names),key=len,reverse=True):
        pattern = r'(?<!\w)' + re.escape(name) + r'(?!\w)'
        if re.search(pattern,remaining):
            matched.append(name)
            remaining=re.sub(pattern,'',remaining)
    punctuation_only = not re.search(r"""[^\s,;|'"\[\]()•]+""",remaining)
    covered = all(
        len(re.findall(r'(?<!\w)'+re.escape(name)+r'(?!\w)',body))
        >= max(1,len(re.findall(r'(?<!\w)'+re.escape(name)+r'(?!\w)',source)))
        for name in matched)
    if matched and punctuation_only and covered and last not in source:
        return body.rstrip()
    return target
