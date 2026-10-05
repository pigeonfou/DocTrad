# Administration

Compte administrateur demandé à l’installation, sans mot de passe par défaut. La page Système affiche le diagnostic et les modèles locaux. Activation/désactivation/benchmark/défaut s’effectuent actuellement par CLI ; les boutons web sont à réaliser.

Commandes d’exploitation prévues par l’installateur :

```bash
sudo /opt/docutranslate/bin/diagnose
sudo /opt/docutranslate/bin/docutranslate-health
sudo /opt/docutranslate/bin/docutranslate-model list
sudo /opt/docutranslate/bin/benchmark-models
```

Les wrappers chargent la configuration protégée et exécutent le code sous le compte de service. Leur installation reste à valider sur Ubuntu natif.

Depuis un shell root sur le serveur :

```bash
set -a
source /etc/docutranslate/docutranslate.env
set +a
runuser -u docutranslate -- /opt/docutranslate/current/.venv/bin/docutranslate diagnose
runuser -u docutranslate -- /opt/docutranslate/current/.venv/bin/docutranslate model list
```

Remplacer la dernière commande par `create-user NOM`, `model verify ID`, `model benchmark ID`, `model set-default ID`, etc. Les mots de passe sont demandés interactivement. Ne pas imprimer le fichier d’environnement.

`/health` distingue disponibilité web/DB/stockage et `ready` ; un HTTP 200 ne prouve pas la présence d’un modèle. `docutranslate health` est un contrôle d’exploitation plus strict. La présence d’un modèle ne prouve pas la qualité : benchmark réel obligatoire.

Un worker interrompu laisse un job en cours. Stopper le worker, inspecter l’état, puis `docutranslate recover ID` et redémarrer. La récupération supprime les segments partiels et relance la traduction avec la révision figée. Ne pas l’utiliser pour récupérer des corrections/exportations importantes : sauvegarder au préalable et traiter manuellement ce cas.

Rétention/suppression automatique, quotas utilisateurs, écran de gestion des comptes et session révocable centralisée restent à implémenter.
