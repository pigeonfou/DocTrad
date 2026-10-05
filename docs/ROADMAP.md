# Travail restant avant validation V1

Les exigences originales restent dans MISSION.md. Cette version est un développement partiel, pas une V1 répondant aux 104 sections.

| Phase | État et travail restant |
|---|---|
| Socle natif | Application testée ; installation systemd/Nginx/PostgreSQL/HTTPS sur véritable Ubuntu et concurrence DB à valider |
| Moteur léger | Interface et CPU synthétique testés ; préparer OPUS réel, valider placeholders et vraie traduction |
| Alternatives | Adaptateurs présents ; installer M2M100/MADLAD, benchmark réel, RAM/VRAM, qualité humaine et métriques |
| Documents | DOCX/PPTX validés sur fixtures ; intégrer Docling et préserver tableaux/illustrations/pages des PDF |
| OCR | Tesseract CPU testé ; tester Paddle local et modèle/manifests/checksums ; améliorer scans mixtes et TIFF multipage |
| Reconstruction | Exports textuels fonctionnels ; conserver structure PDF/images, styles mixtes Office et caractères Unicode étendus |
| Annotations images | Extraction OCR présente ; option UI, inpainting/replacement graphique, original et contrôle de confiance à réaliser |
| Qualité | Protection et mémoire testées ; segmentation contextuelle par modèle, score qualité, BLEU/chrF, corpus étoffé |
| Offline | Variables et garde réseau de tests ; bundle complet DEB/wheels/modèles, closure APT, signatures et vraie installation isolée/redémarrage |
| Industrialisation | Scripts présents ; Alembic, restauration/rollback réels, rétention/quota, audit CVE, plafonds CPU/mémoire, monitoring, compte/session administration |

Autres écarts : logrotate non nécessaire actuellement (journald prévu), écrans administrateur de mutation de modèles encore absents, sélection automatique complète selon matériel/file/document à ajouter, post-édition LLM facultative non implémentée.

Ordre de reprise : obtenir les checkpoints officiels → OPUS réel sur CPU → vérifier protection technique/glossaire → deux autres modèles → Ubuntu natif → Docling/Paddle et reconstruction enrichie → bundle/redémarrage isolé → production. Aucun résultat benchmark ni V1 validée ne doit être annoncé avant les tests correspondants.
