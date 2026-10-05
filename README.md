# DocTrad — traduction documentaire locale

Application web native destinée à Ubuntu Server 24.04 amd64, anglais → français, sans conteneur en production. Version **0.1.0 de développement : la V1 complète n’est pas encore validée**.

## Ce qui est réalisé

- FastAPI, comptes locaux Argon2id, sessions HTTPS, CSRF, séparation des documents par utilisateur.
- File PostgreSQL avec réservation transactionnelle `FOR UPDATE SKIP LOCKED`. Un worker par défaut ; Redis n’est pas nécessaire.
- Service unique de traduction locale Transformers : adaptateurs OPUS-MT, M2M100 et MADLAD, modèles sélectionnables, révision figée par job, contrôle SHA256 et licence permissive.
- Protection des références, nombres et unités, glossaire exact, mémoire des corrections par utilisateur, historique de post-édition et réexport.
- DOCX et PPTX : extraction et réinjection dans paragraphes/tableaux ; conservation des images embarquées. Styles mixtes d’un paragraphe susceptibles d’être simplifiés.
- PDF natif et scans/images via OCR Tesseract local sur CPU. Coordonnées et confiance OCR stockées ; alertes sous 85 %.
- Export DOCX et PDF recomposé ; export PPTX pour une source PPTX.
- Configurations Nginx HTTPS/systemd, installation native, scripts de préparation des modèles, diagnostic, sauvegarde/restauration, mise à jour/rollback.

## Limites actuelles

**Aucun poids de traduction réel installé ni benchmark qualité exécuté dans l’environnement de réalisation.** Les tests de modèle CPU utilisent un petit réseau non entraîné, uniquement pour contrôler le chargement et l’inférence locale. Les tests complets de traitement utilisent une mémoire de traductions fictives validées. Ils ne constituent pas une validation de traduction IA.

Le serveur cible n’a pas été déployé. L’installation systemd/PostgreSQL/Nginx, la restauration, le rollback et le bundle isolé complet restent à tester sur une véritable machine Ubuntu. Docling et PaddleOCR sont des adaptateurs expérimentaux non intégrés au parcours validé. Les images/PDF recomposés ne conservent pas la mise en page ni les illustrations de l’original ; celui-ci reste conservé. Le remplacement graphique des annotations n’est pas réalisé.

## Démarrage de développement

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install --no-deps --no-build-isolation -e .
.venv/bin/pytest -q
```

Les tests utilisent SQLite uniquement pour isoler les validations applicatives. **La production utilise PostgreSQL** ; les tests de concurrence PostgreSQL restent à exécuter.

Pour installer sur un serveur dédié, lire [INSTALL_UBUNTU_24_04.md](docs/INSTALL_UBUNTU_24_04.md) avant `sudo ./install.sh`. L’installation n’installe aucun modèle implicitement. Préparer et transférer au moins un modèle avant d’attendre une traduction.

## Documentation

- [Rapport factuel de réalisation](docs/IMPLEMENTATION_REPORT.md)
- [Architecture](docs/ARCHITECTURE.md) · [Sécurité](docs/SECURITY.md)
- [Installation native](docs/INSTALL_UBUNTU_24_04.md) · [Installation isolée](docs/OFFLINE_INSTALL.md)
- [Modèles](docs/MODELS.md) · [Benchmarks](docs/MODEL_BENCHMARKS.md) · [GPU](docs/GPU_INSTALL.md)
- [Guide utilisateur](docs/USER_GUIDE.md) · [Administration](docs/ADMIN_GUIDE.md)
- [Sauvegarde/restauration](docs/BACKUP_RESTORE.md) · [Mise à jour](docs/UPDATE.md) · [Rollback](docs/ROLLBACK.md)
- [Diagnostic](docs/TROUBLESHOOTING.md) · [Licences](docs/LICENSES.md)
- [Cahier des charges original](docs/MISSION.md) · [Travail restant](docs/ROADMAP.md)
