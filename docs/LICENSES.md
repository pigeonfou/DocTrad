# Licences — vérification du 5 octobre 2026

Les licences des candidats ont été consultées sur leurs fiches officielles. Le téléchargement, l’import et la sélection ne sont pas bloqués par la licence. La valeur annoncée par la révision est conservée à titre informatif, y compris lorsqu’elle est absente ou différente du catalogue. Conserver les notices originales dans chaque bundle. Les droits sur les données d’entraînement et l’adéquation à votre usage ne peuvent pas être déduits du seul nom d’une licence.

| Candidat | Source officielle | Licence publiée | Usage/décision |
|---|---|---|---|
| OPUS-MT EN→FR | https://huggingface.co/Helsinki-NLP/opus-mt-en-fr | Apache-2.0 | Candidat professionnel ; notices à conserver |
| M2M100 418M | https://huggingface.co/facebook/m2m100_418M | MIT | Candidat professionnel ; notices à conserver |
| MADLAD-400 3B MT | https://huggingface.co/google/madlad400-3b-mt | Apache-2.0 | Candidat professionnel ; notices à conserver |
| NLLB distilled 600M | https://huggingface.co/facebook/nllb-200-distilled-600M | CC-BY-NC-4.0 | Non commercial ; exclu du défaut et du registre permissif |
| TranslateGemma 4B | https://huggingface.co/google/translategemma-4b-it | Conditions Gemma, accord demandé | Analyse spécifique nécessaire ; non implémenté |
| Hunyuan-MT-7B | https://huggingface.co/tencent/Hunyuan-MT-7B | Licence spécifique à analyser sur la révision | Statut inconnu ; non implémenté |

Les versions effectivement installées et champs de licence/source de **toutes les distributions Python** sont inventoriés dans [COMPONENT_LICENSES.json](COMPONENT_LICENSES.json), directement depuis leurs métadonnées locales. Un champ absent n’équivaut pas à une permission. Cet inventaire ne remplace pas la collecte des textes complets ni une validation de redistribution.

FastAPI, SQLAlchemy, Jinja2, PyTorch, Transformers, bibliothèques Office/PDF et autres : utiliser les noms/versions exacts de `requirements.lock`, conserver les fichiers LICENSE/NOTICE des wheels. PostgreSQL/Nginx/Tesseract/Poppler : conserver les fichiers `/usr/share/doc/PAQUET/copyright` de chaque DEB préparé ; l’audit complet des versions système n’est pas terminé.

Docling/PaddleOCR ne sont pas installés dans le parcours validé. Leurs versions et licences détaillées restent à figer avec leurs modèles. Aucune autorisation de redistribution de ces modèles n’est supposée.

La licence de distribution du code propre de ce dépôt n’a pas été attribuée : elle reste à définir par son propriétaire avant une diffusion à des tiers. Le dépôt public ne signifie pas automatiquement licence permissive.

