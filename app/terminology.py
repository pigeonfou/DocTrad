"""Terminologie technique EN→FR, entièrement locale.

Ne traduire ici que les termes non ambigus. Les noms commerciaux et
identifiants restent inchangés. Le glossaire utilisateur a priorité.
"""
DEFAULT_TERMS = {
    "PLI": "PLI",
    "Network Resilience": "Résilience du réseau",
    "Scalability and Spectrum Efficiency": "Évolutivité et efficacité spectrale",
    "Global Mobility": "Mobilité mondiale",
    "Multi-vendor Ecosystem": "Écosystème multifournisseur",
    "Spatial Hops": "Sauts spatiaux",
    "Bandwidths": "Largeurs de bande",
    "Scalability": "Évolutivité",
    "Software Defined Radio": "radio logicielle",
    "Position Location Information": "informations de position",
    "End User Device": "Terminal utilisateur",
    "Black Relay": "Relais noir",
    "Power supply": "alimentation électrique",
    "File transfer": "Transfert de fichiers",
    "Supported Software Defined Radio (SDR) Platforms": "Plateformes SDR prises en charge",
    "Technical Features": "Caractéristiques techniques",
    "Features": "Caractéristiques",
    "Capability": "Capacités",
    "Capabilities": "Capacités",
    "Technology Readiness Level": "niveau de maturité technologique",
    "Frequencies": "Fréquences",
    "Security": "Sécurité",
    "Modulation": "Modulation",
    "Data": "Données",
    "Voice": "Voix",
    "Product Specification Sheet": "Fiche de spécifications produit",
    "THE TRELLISWARE TSM WAVEFORM": "LE TSM WAVEFORM DE TRELLISWARE",
    "TRELLISWARE'S TSM WAVEFORM IS THE INDUSTRY STANDARD FOR RESILIENT COMMUNICATIONS": "TSM WAVEFORM DE TRELLISWARE : LA RÉFÉRENCE DU SECTEUR POUR LES COMMUNICATIONS RÉSILIENTES",
    "TECHNICAL FEATURES OF THE": "CARACTÉRISTIQUES TECHNIQUES DU",
    "End User Device (EUD) Support": "Terminaux utilisateur (EUD) pris en charge",
    "Chat": "Messagerie instantanée",
    "SCAN ME": "SCANNEZ-MOI",
    "SD and HD video": "Vidéo SD et HD",
}
# Ces appellations ne sont ni francisées ni remplacées par des synonymes.
PROTECTED_NAMES = (
    "TrellisWare", "TSM WAVEFORM", "TSM-X", "TSM",
    "Shadow Radio", "Ghost Radio", "Spirit Radio",
    "Shadow High Power Radio", "Shadow Core Board Module",
    "Ghost Embedded Module", "Tactical Assault Kit",
    "Collins Aerospace", "L3Harris", "Thales Defense & Security",
    "Ultra", "ORION X510", "WinTAK", "ATAK", "MANET", "MELPe",
    "WREN", "SOCOM", "Protobuf", "Android", "Windows", "NSA", "SDR",
    "When Nothing Else Works",
    "National Security Agency", "WREN Security", "WREN Information Security",
    "SOCOM Tactical Communications", "STC Security",
)


def preserved_name(text):
    """Recognize standalone marks even when OCR inserts spaces in a logo."""
    import re
    normalized = re.sub(r'\W+', '', text).casefold()
    if any(normalized == re.sub(r'\W+', '', name).casefold() for name in PROTECTED_NAMES):
        return True
    # Only isolated brand lettering, never a prose sentence or product list.
    from difflib import SequenceMatcher
    return (8 <= len(normalized) <= 13
            and normalized.startswith('trel') and normalized.endswith('ware')
            and SequenceMatcher(None, normalized, 'trellisware').ratio() >= .80)


def reference_label(text, terms):
    """Product/reference lists contain nothing that needs prose inference."""
    import re
    # Internet/contact identifiers and postal directory entries are metadata.
    if re.fullmatch(r'\s*(?:\d+\s*\|\s*)?(?:[\w.+-]+@)?[\w-]+(?:\.[\w-]+)+\s*', text):
        return True
    if re.match(r'^TrellisWare Technologies, Inc\.\s+\d+\s', text):
        return True
    if re.match(r'^\d{1,6}\s', text) and re.search(r'\b(?:Street|Court|Road|Suite|Avenue)\b', text):
        return True
    if re.match(r'^(?:Tel\.?|Phone)\s', text) and ('@' in text or 'www' in text):
        return True
    remaining = text
    found = False
    for name in sorted(PROTECTED_NAMES, key=len, reverse=True):
        # Explicit user translations take precedence over mark preservation.
        if terms.get(name, name) != name:
            continue
        remaining, count = re.subn(r'(?<!\w)' + re.escape(name) + r'(?!\w)', '', remaining)
        found |= bool(count)
    remaining = re.sub(r'\b[A-Z0-9]+(?:[-/][A-Z0-9]+)+\b|\b[A-Z]{2,}\b', '', remaining)
    return found and not re.search(r'\w', remaining)


def restore_anchored_numbers(source, target):
    """Restore an omitted value only at a unique, unchanged acronym anchor."""
    import re
    for match in re.finditer(r'(\([A-Z]{2,10}\))\s+(\d+(?:[.,]\d+)?)\b', source):
        anchor, number = match.groups()
        if source.count(anchor) == target.count(anchor) == 1:
            pattern = re.escape(anchor) + r'(?!\s*\d)'
            target = re.sub(pattern, lambda _: anchor + ' ' + number, target)
    return target


def restore_dual_measurements(source, target):
    """Retain both source units when a model drops one side of a conversion.

    Only an unchanged, unique secondary measurement anchors restoration.
    Existing primary numbers, ambiguous anchors and changed units stay for QA.
    """
    import re
    from decimal import Decimal
    number = r'[+-]?\d+(?:[.,]\d+)?'
    pairs = {('miles', 'km'), ('mile', 'km'), ('ft', 'm'), ('in', 'mm'),
             ('inch', 'mm'), ('inches', 'mm'), ('lb', 'kg'), ('lbs', 'kg')}
    pattern = re.compile(r'(?<!\w)(' + number + r')\s*(miles|mile|ft|inches|inch|in|lbs|lb)\s*\(\s*(' + number + r')\s*(km|mm|kg|m)\s*\)')
    for match in pattern.finditer(source):
        primary, unit, secondary, secondary_unit = match.groups()
        if (unit, secondary_unit) not in pairs:
            continue
        # Never duplicate a value already present, including a changed unit.
        present = {Decimal(value.replace(',', '.')) for value in re.findall(number, target)}
        if Decimal(primary.replace(',', '.')) in present:
            continue
        anchor_number = re.escape(secondary.replace(',', '.')).replace(r'\.', '[.,]')
        anchor = re.compile(r'(?<![\w.,])' + anchor_number + r'\s*' + secondary_unit + r'(?!\w)')
        source_anchors, target_anchors = list(anchor.finditer(source)), list(anchor.finditer(target))
        if len(source_anchors) != 1 or len(target_anchors) != 1:
            continue
        retained = target_anchors[0]
        a, b = retained.span()
        localized = primary.replace('.', ',') if ',' in retained[0] else primary
        replacement = localized + ' ' + unit + ' (' + retained[0] + ')'
        if a and b < len(target) and target[a-1] == '(' and target[b] == ')':
            a -= 1; b += 1
        target = target[:a] + replacement + target[b:]
    return target

def terminology(user_terms=None):
    terms = dict(DEFAULT_TERMS)
    terms.update({name: name for name in PROTECTED_NAMES})
    terms.update(user_terms or {})
    return terms



def correct_network_terms(source, target):
    """Correct observed ambiguous translations only in their source context."""
    import re
    for operator, value in re.findall(r'([<>≤≥])\s*(\d+(?:[.,]\d+)?)', source):
        numeric = r'(?<![\w.,])' + re.escape(value.replace(',', '.')).replace(r'\.', '[.,]') + r'(?![\w.,\d])'
        source_values, target_values = list(re.finditer(numeric, source)), list(re.finditer(numeric, target))
        if len(source_values) == len(target_values) == 1:
            anchor = target_values[0]
            prefix = target[:anchor.start()].rstrip()
            if not prefix.endswith(('<', '>', '≤', '≥')):
                target = target[:anchor.start()] + operator + ' ' + target[anchor.start():]
    for email in re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', source):
        collapsed = email.replace('@', '')
        if email not in target and target.count(collapsed) == 1:
            target = target.replace(collapsed, email)
    if 'Android™' in source:
        target = re.sub(r'\bAndroidTM\b', 'Android™', target)
    if re.search(r'\bhops?\b', source, re.I):
        target = re.sub(r'\bhoublon(s?)\b', lambda m: 'saut' + m[1], target, flags=re.I)
    if re.search(r'\bSoftware Defined Radio\b', source, re.I):
        target = re.sub(r'\bradio définie par (?:le )?logiciel\b', 'radio logicielle', target, flags=re.I)
    if re.search(r'\bSDRs?\b', source):
        target = re.sub(r'\bDTS\b', 'SDR', target)
    if (re.match(r'^Multi-vendor Ecosystem\s*[-–—]+', source)
            and re.match(r'^En tant que\b', target)):
        target = 'Écosystème multifournisseur — ' + target
    if re.search(r'\bTRL\b', source):
        target = re.sub(r'\bTMT\b', 'TRL', target)
    if 'Technology Readiness Level' in source:
        target = re.sub(r'niveau de préparation technologique', 'niveau de maturité technologique', target, flags=re.I)
    if re.search(r'program of record tactical radios', source, re.I):
        target = re.sub(r'programmes de radios tactiques record', 'radios tactiques de programmes officiels', target, flags=re.I)
    if 'simultaneous voice, data, video, and Position Location Information (PLI)' in source:
        target = re.sub(r'des informations de localisation simultanées de voix, de données, de vidéo et de position \(PLI\)',
                        'la transmission simultanée de la voix, des données, de la vidéo et des informations de position (PLI)', target, flags=re.I)
    return restore_dual_measurements(source, restore_anchored_numbers(source, target))

