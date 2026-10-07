# Télécharger et installer les modèles locaux

## Depuis DocTrad

1. Se connecter avec un compte administrateur.
2. Ouvrir **Système & modèles**.
3. Choisir **OPUS anglais → français** pour commencer sur CPU.
4. Cocher l'autorisation du téléchargement initial depuis Internet.
5. Cliquer **Télécharger et installer le modèle**.
6. Attendre l'état **Modèle local installé**. Le modèle apparaît dans la liste.
7. Revenir à Documents et lancer une traduction avec le profil Rapide ou Automatique.

Le suivi se met à jour sans bloquer la page. Les fichiers temporaires sont placés sur
le disque dans le dossier des modèles, pas dans `/tmp`. Un seul téléchargement est
actif à la fois. Après interruption, relancer : les fichiers partiels sont conservés
et la reprise conserve la révision exacte. Aucun modèle installé n'est remplacé.

| Choix | Utilisation | Mémoire indicative | Marge disque proposée |
|---|---|---:|---:|
| OPUS anglais → français | Commencer sur CPU | 1 Go | 1 Go |
| M2M100 418M | Traduction multilingue | 4 Go | 3 Go |
| MADLAD400 3B | Modèle volumineux | 16 Go | 8 Go |

Les valeurs sont des estimations de préparation, pas une garantie de performances.
La sélection pour une traduction continue à respecter la mémoire disponible.

## Hors ligne et données

Le clic autorise seulement la récupération de métadonnées, poids et tokenizers publics
sur Hugging Face et ses hôtes de stockage. Aucun document, texte utilisateur, secret de
session, mot de passe de base ou token privé n'est transmis au processus de préparation.
La télémétrie du Hub est désactivée. L'environnement hors ligne des services reste inchangé.
Le moteur continue à utiliser `local_files_only=True` et `trust_remote_code=False`.
Aucune API de traduction distante n'est utilisée.

La source est limitée à trois dépôts officiels. La révision récupérée est figée au SHA
exact, la licence attendue est contrôlée, et seuls les poids Safetensors sont acceptés.
Les empreintes LFS SHA-256 de la source sont comparées lorsqu'elles sont disponibles ;
le manifeste local conserve les empreintes de tous les fichiers. Le dossier est publié
atomiquement une fois vérifié. Une erreur conserve les poids incomplets pour la reprise.

Une machine complètement isolée peut continuer à utiliser `scripts/prepare-model.py`
sur une machine connectée, puis la procédure d'import de modèles locaux.

## En ligne de commande

Dans l'environnement Python DocTrad, avec un dossier appartenant à l'utilisateur applicatif :

```bash
python -m app.model_download opus-mt-en-fr \
  --model-root /var/lib/oneforall/doctrad/models --allow-network
```

`--allow-network` est obligatoire. Pour une version imposée, ajouter `--revision <SHA-40>`.
Ne pas exécuter cette commande sous root pour un dossier utilisé par un service non root.
L'installation autonome autorise le dossier `/opt/docutranslate/models/translation`
dans le sandbox du service web ; l'installation OneForAll utilise son dossier de données.

## Dépannage

- Réseau indisponible : vérifier l'accès sortant HTTPS à Hugging Face et au stockage des poids,
  puis relancer le téléchargement ; les services de traduction restent hors ligne.
- Dossier non accessible : vérifier le propriétaire et `ReadWritePaths` du service web.
- Modèle existant invalide : restaurer une sauvegarde ou importer une version vérifiée ;
  la commande n'efface pas automatiquement les fichiers.
- Manque de disque : libérer de l'espace dans le volume des modèles, puis reprendre.
- Révision sans Safetensors ou licence différente : téléchargement refusé avant les poids.

## Validation de cette évolution

Tests locaux avec Hub simulé : publication atomique, reprise/idempotence, verrou,
contrôle du disque, licence, refus des poids pickle, empreintes, absence de secrets dans
le processus, authentification admin, CSRF et autorisation réseau. Aucun gros modèle n'a
été téléchargé dans l'environnement de développement : le téléchargement réel et une
traduction restent à vérifier sur le serveur après déploiement.
