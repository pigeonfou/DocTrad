# Installation via OneForAll

Le dépôt fournit deux modes distincts : autonome sur serveur dédié (guide du README, branche `main`) et instance gérée par OneForAll (branche `main`, contrat `packaging/oneforall.json`).

## Installer une instance gérée

1. Préparer OneForAll selon [son guide Ubuntu](https://github.com/pigeonfou/OneForAll/blob/main/docs/installation-ubuntu.md), configurer le LAN, puis installer le socle.
2. Autoriser la lecture du dépôt `pigeonfou/DocTrad` : clé de déploiement en lecture seule dans `/etc/oneforall/git/doctrad.key`, clé publique enregistrée dans GitHub, clés d’hôte GitHub vérifiées. Voir le guide GitHub/Cloudflare OneForAll.
3. Lancer `sudo bash install-oneforall.sh` depuis le dépôt OneForAll, choisir 3, puis `doctrad` et saisir le mot de passe administrateur. Le compte initial est `admin`.
4. Exécuter `sudo bash install-oneforall.sh status`. Configurer les modèles ou OpenCascade quand nécessaire et tester les parcours métier.

Le code est conservé sous `/opt/oneforall/apps/doctrad/releases/<SHA>`, les données sous `/var/lib/oneforall/doctrad` et les services portent le préfixe `oneforall-doctrad-`. Le frontal utilise des sous-domaines ou, avec `routing_mode=paths`, le chemin `/doctrad/` derrière le portail commun. L’accueil LAN accepte l’IP du serveur.

## Mise à jour et récupération

```bash
sudo bash install-oneforall.sh update --apps doctrad
sudo bash install-oneforall.sh logs --apps doctrad
sudo bash install-oneforall.sh backup --apps doctrad
```

La commande update récupère la tête de `main`. Pour restaurer, utiliser le choix 10 ou la commande `restore` avec le snapshot et confirmation, selon le guide sauvegarde/restauration OneForAll. Les états sont vérifiés par les contrôles HTTP et applicatifs ; un service actif ne garantit pas le bon résultat métier.

Ne pas lancer l’installateur, le runner ou les scripts de mise à jour autonomes sur cette instance : ils ciblent d’autres chemins. Une installation historique doit être importée avec le choix 13 après sauvegarde, jamais écrasée. Pour héberger cette application sur un autre serveur, l’administration LAN du portail peut configurer son URL directement ; ce réglage ne déplace ni données ni services.

## Vérification

Les scripts et tests automatisés sont contrôlés lors de l’intégration. Une nouvelle installation complète Ubuntu 24/26, les accès Git privés, la configuration réseau et une restauration réelle restent à valider sur le serveur choisi.
