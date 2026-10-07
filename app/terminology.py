"""Terminologie technique EN→FR, entièrement locale.

Ne traduire ici que les termes non ambigus. Les noms commerciaux et
identifiants restent inchangés. Le glossaire utilisateur a priorité.
"""
DEFAULT_TERMS = {
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
    "Supported Software Defined Radio (SDR) Platforms": "Plateformes de radio logicielle (SDR) prises en charge",
    "Technical Features": "Caractéristiques techniques",
    "Features": "Caractéristiques",
    "Capability": "Capacités",
    "Frequencies": "Fréquences",
    "Security": "Sécurité",
    "Modulation": "Modulation",
    "Data": "Données",
    "Voice": "Voix",
}
# Ces appellations ne sont ni francisées ni remplacées par des synonymes.
PROTECTED_NAMES = (
    "TrellisWare", "TSM WAVEFORM", "TSM-X", "TSM",
    "Shadow Radio", "Ghost Radio", "Spirit Radio",
    "Shadow High Power Radio", "Shadow Core Board Module",
    "Ghost Embedded Module", "Tactical Assault Kit",
    "Collins Aerospace", "L3Harris", "Thales Defense & Security",
    "Ultra", "ORION X510", "WinTAK", "ATAK", "MANET", "MELPe",
    "WREN", "SOCOM", "Protobuf",
)

def terminology(user_terms=None):
    terms = dict(DEFAULT_TERMS)
    terms.update({name: name for name in PROTECTED_NAMES})
    terms.update(user_terms or {})
    return terms
