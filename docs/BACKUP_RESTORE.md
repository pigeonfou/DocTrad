# Sauvegarde et restauration

Scripts fournis, syntaxe validée, exécution réelle PostgreSQL/systemd non testée.

```bash
sudo scripts/backup.sh /var/backups/docutranslate/backup-unique --include-documents --include-models
sudo scripts/restore.sh /var/backups/docutranslate/backup-unique --replace-existing
```

Les services sont arrêtés pour une sauvegarde cohérente. `pg_dump -Fc` couvre comptes applicatifs, jobs, segments, historique, mémoire, glossaire et benchmarks. La configuration et la release courante sont incluses. Les documents et modèles sont facultatifs ; sans eux, la DB seule ne suffit pas à restituer tous les résultats ni à retraduire.

Le backup contient des secrets et données ; permissions et chiffrement à la charge de l’administrateur. Les checksums actuels couvrent le dump et le pointeur de release ; ajouter l’inventaire intégral et la signature avant distribution industrielle. Tester une restauration sur un serveur de validation. Le cluster restauré doit disposer du rôle `docutranslate`, PostgreSQL compatible et de la même configuration de mot de passe.

La restauration remplace DB/configuration et éventuellement fichiers. Elle ne bascule pas automatiquement la release applicative : vérifier la compatibilité et utiliser le rollback si nécessaire. Si la restauration échoue, les services restent arrêtés pour éviter de servir des données incohérentes.
