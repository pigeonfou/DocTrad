# Rollback

Conserver au moins deux releases. Après confirmation de la compatibilité DB :

```bash
sudo scripts/rollback.sh 0.1.0 --schema-compatible
```

Les services sont arrêtés, le symlink bascule atomiquement et les services redémarrent. Le healthcheck web est vérifié ; refaire une traduction et un téléchargement. Une migration incompatible impose une restauration du backup et des fichiers, pas seulement un ancien code. Script non validé sur serveur réel.
