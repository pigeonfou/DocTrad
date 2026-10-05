# Rapport factuel — 5 octobre 2026

## État

Développement 0.1.0 poussé dans le dépôt demandé. Accès écriture GitHub confirmé par un commit réel du cahier des charges. Cette version ne valide pas encore la V1 complète.

## Environnement

Ubuntu 24.04.3 amd64, Python 3.12.14, environ 9,7 Gio RAM, aucun GPU utilisable. Dépendances installées dans `.venv`, vérifiées et verrouillées dans `requirements.lock`. PyTorch 2.14.1+cu130, Transformers 5.18.0, FastAPI 0.142.2, SQLAlchemy 2.1.3. Inventaire complet : lock et COMPONENT_LICENSES.json.

## Tests réellement exécutés

- 38 tests pytest réussis localement (un test supplémentaire de concurrence PostgreSQL est réservé à la CI), dont OCR Tesseract réel image et PDF scanné ; fixtures fictives PDF natif, scan, DOCX, PPTX et image générées.
- Références exactes `12 VDC`, `J3`, `STM32F407`, `4.5 Nm`, `M4x20`, `CAN`, `RS-485` contrôlées par tests unitaires de protection/réinjection.
- DOCX : tableau et image embarquée conservés (octets image comparés), traduction textuelle injectée puis export DOCX/PDF vérifié.
- PPTX : extraction/réinjection/export relus.
- Parcours HTTP TestClient : authentification, upload, file, traitement par mémoire validée, téléchargement PDF, correction, historique, réexport DOCX. Le registre du parcours est remplacé par un fixture de test ; aucune qualité IA n’en découle.
- CPU : petit T5 aléatoire non entraîné créé localement, sauvegardé Safetensors, chargé avec AutoTokenizer/AutoModel, inférence puis déchargement, sockets interdits. Test du mécanisme local, pas de traduction.
- Licence restrictive, checksum altéré, modèle désactivé, CSRF, accès interutilisateurs, XSS et archives dangereuses refusés.
- Réseau Python non loopback bloqué pour la suite de tests.
- `pip check`, compilation Python et syntaxe shell contrôlés.
- Serveur Uvicorn lancé réellement et interrogé en HTTP loopback : login, healthcheck, redirection de la page protégée et fichier CSS local vérifiés. `ready` reste faux sans modèle réel.

Un avertissement de dépréciation Starlette/TestClient avec httpx est présent ; les tests passent. L’interface a été exercée par HTTP ; inspection visuelle complète par navigateur non réalisée.

## Échecs et limites de l’environnement

La connexion directe à Hugging Face pour les poids a expiré (curl, délai 15 s). Aucun modèle entraîné installé. Les fiches et licences officielles ont pu être consultées par recherche web, ce qui ne donne pas accès aux fichiers de poids.

APT a récupéré les DEB PostgreSQL 16.15 et Nginx 1.24, mais leur configuration a échoué sur les créations de groupes/chown restreintes de l’environnement. systemd n’y fonctionne pas. Test Nginx : syntaxe acceptée, puis échec environnemental lors du chown d’un répertoire temporaire. Aucun déploiement Ubuntu natif complet validé.

## Modèles et mesures

| Élément | Résultat |
|---|---|
| Modèles entraînés installés | Aucun |
| Modèle recommandé/rapide/qualité | Non déterminé, benchmark requis |
| Qualité EN→FR / BLEU / chrF / COMET | Non mesurée |
| Temps de vraie traduction | Non mesuré |
| RAM/VRAM des modèles | Non mesurée |
| GPU | Indisponible ; accélération non testée |
| Redémarrage isolé LAN complet | Non exécuté |

## Formats et opérations

Parcours testé : DOCX/PPTX et PDF, OCR image/scan, exports DOCX/PDF/PPTX. Les exports PDF et DOCX issus de PDF/images restent des recompositions textuelles. Aucun remplacement des annotations graphiques. Docling/Paddle : adaptateurs expérimentaux non validés. Scripts natifs installation/backup/restore/update/rollback/bundle : écrits et contrôlés syntaxiquement, pas validés en exploitation.

Les guides associés décrivent les commandes et les limites ; ROADMAP liste les écarts. Il n’est pas justifié de déclarer le système prêt pour production ni l’ensemble de la mission terminé.
