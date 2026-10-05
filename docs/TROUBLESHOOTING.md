# Diagnostic

`docutranslate diagnose` : OS/Python, CPU/cœurs, RAM, disque, DB, file, heartbeat worker, runtime, GPU et OCR. Les champs kernel/swap/pilote/CUDA/VRAM détaillés restent à ajouter. `journalctl -u docutranslate-worker -u docutranslate-web -u docutranslate-translation` pour les services.

- Aucun modèle : transférer un manifest et les fichiers complets, vérifier SHA256/licence/révision ; aucun téléchargement de secours.
- Modèle invalidé : contrôler checksums, droits, famille supportée et politique permissive.
- Refus automatique : contrôler RAM disponible et besoin déclaré dans le manifest.
- Référence protégée modifiée : le segment échoue ; évaluer le moteur et améliorer le mécanisme de protection, ne pas accepter silencieusement l’altération.
- OCR absent : installer Tesseract et `eng.traineddata` localement ou configurer l’adaptateur Paddle après validation.
- Job bloqué après panne : voir ADMIN_GUIDE et sauvegarder avant récupération.
- HTTPS : vérifier nom/SAN/confiance PKI, Nginx et cookie Secure.
- Installation interrompue : ne pas relancer aveuglément ; inspecter users/DB/config/releases. Le script n’est pas encore idempotent.

Dans l’environnement Work, systemd ne démarre pas ; l’installation des paquets serveur échoue lors de la création des groupes/chown. Ces limites concernent l’environnement de réalisation et ne constituent pas une preuve de fonctionnement du script sur le serveur cible.
