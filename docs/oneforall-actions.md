# Déploiement Actions sur le serveur DocTrad / OneForAll

Les tests s'exécutent sur un runner GitHub hébergé pour les dépôts publics comme
privés. Les pull requests n'exécutent aucun code sur le serveur DocTrad. Un push
sur `main` ne déclenche le déploiement qu'après réussite de `DocTrad checks`.
Les commits déjà dépassés par un autre commit sur `main` sont ignorés.

Le job de déploiement utilise un runner enregistré dans `pigeonfou/DocTrad`, avec
les labels `self-hosted`, `Linux`, `X64`, `doctrad-deploy`. Il n'effectue aucun
checkout de code sur le serveur. La commande privilégiée est un programme fixe,
détenu par root, limité à DocTrad et à un SHA complet, avec environnement nettoyé.
Elle appelle le gestionnaire OneForAll installé et vérifie encore le SHA de main
avant de lancer `update --apps doctrad --sha SHA`.

## Préparation unique du serveur

Après une mise à jour manuelle vers la version contenant ces scripts, exécuter :

```bash
sudo bash /opt/oneforall/apps/doctrad/current/scripts/setup-oneforall-runner.sh
```

Le compte d'un unique service runner DocTrad existant est détecté automatiquement.
Sinon le compte `oneforall-runner` est préparé. Pour choisir un autre compte,
le passer explicitement en argument, par exemple `docutranslate-runner`.
Le compte transmis doit être celui indiqué par `User=` dans son unité systemd.
Le script installe `/usr/local/sbin/oneforall-doctrad-deploy` et son autorisation
sudo dédiée. Il vérifie le diagnostic sans mot de passe et liste les services
de runner. Il ne télécharge pas de runner et n'enregistre aucun jeton GitHub.

Si aucun runner n'est enregistré, utiliser **Settings → Actions → Runners → New
self-hosted runner** dans le dépôt DocTrad. Exécuter les commandes proposées sous
le compte préparé, ajouter le label `doctrad-deploy`, puis installer et démarrer
le service avec `sudo ./svc.sh install COMPTE` et `sudo ./svc.sh start` depuis
le répertoire du runner. Si le runner existe mais est rattaché à un autre dépôt,
il faut un enregistrement dédié au dépôt DocTrad.

## Vérification

```bash
sudo systemctl list-unit-files --type=service --no-pager | grep 'actions.runner.'
sudo systemctl status 'actions.runner.*' --no-pager -l
sudo -u oneforall-runner sudo -n /usr/local/sbin/oneforall-doctrad-deploy --status
```

Le runner doit être **Idle** ou **Active** dans GitHub et le service doit être
**active (running)**. La présence du workflow seule ne prouve pas sa connexion.
Une exécution `queued` après réussite des tests signifie qu'aucun runner
disponible ne correspond aux labels requis. Une erreur sudo ou « command not
found » signifie que la préparation locale reste à effectuer.

Le workflow `DocTrad local model` concerne l'ancienne installation autonome et
reste conditionné aux dépôts privés. OneForAll conserve les modèles déjà
installés ; ce workflow n'est pas requis pour le déploiement public décrit ici.

La récupération des documents publics de référence et les essais complets via
le worker sont décrits dans [Chaîne autonome](autonomous-reference-chain.md).
