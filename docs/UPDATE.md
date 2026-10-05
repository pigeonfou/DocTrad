# Mise à jour

Script natif fourni, non testé sur une installation réelle. Préparer une release relue et un wheelhouse complet, sauvegarder puis :

```bash
sudo scripts/update.sh /chemin/source 0.1.1 /chemin/wheelhouse
```

Le script crée une nouvelle release/venv, installe exclusivement les wheels locales, vérifie les dépendances et la syntaxe Python, arrête les services, initialise le schéma puis bascule `current` atomiquement. Si le healthcheck web échoue, il rétablit l’ancien symlink et redémarre les services.

Avant toute évolution du schéma, ajouter des migrations versionnées et une compatibilité explicite. La restauration DB n’est pas automatique. Les tests de traitement réels et de modèle doivent être exécutés avant la bascule ; `compileall`/`pip check` ne suffisent pas. Les units systemd et paramètres Nginx ne sont pas remplacés automatiquement par ce script ; appliquer leurs changements explicitement et les vérifier.
