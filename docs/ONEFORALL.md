# Intégration OneForAll

Cette branche ajoute le contrat `packaging/oneforall.json` utilisé par l’installateur OneForAll. L’installation autonome historique reste disponible. Ne pas exécuter son installateur historique pour une instance OneForAll.

OneForAll conserve le code dans des versions immuables sous `/opt/oneforall/apps/doctrad/releases/<SHA>` et les données dans `/var/lib/oneforall/doctrad`. Son frontal Nginx dédié donne accès à l’application par sous-domaine, sans réécriture de ses routes.

Les mises à jour sont réalisées par la commande root installée par OneForAll ; elles ne passent pas par les anciens workflows qui ciblent les chemins historiques. Ne pas lancer les deux chaînes pour une même instance.

Les tests d’installation sur Ubuntu 24.04 et 26.04, les migrations de données et la recette métier doivent être exécutés sur les serveurs concernés. Aucun déploiement réel n’est déclaré par cette adaptation.
