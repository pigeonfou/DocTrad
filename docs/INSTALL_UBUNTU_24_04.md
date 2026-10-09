# Installation native Ubuntu 24.04 / 26.04

Cible autonome : serveur dédié Ubuntu x86_64. Ubuntu 24.04 est la cible initiale ; Ubuntu 26.04 exige `--experimental-ubuntu26` et la validation des dépendances sur le serveur. Les contrôles de code ne remplacent pas une installation complète ni une traduction avec un modèle réel. Pour l’installation gérée, utiliser [ONEFORALL.md](ONEFORALL.md).

1. Cloner le dépôt, vérifier `requirements.lock`, lire SECURITY et LICENSES.
2. Préparer un modèle sur une machine connectée : voir MODELS. Les téléchargements de dépendances et poids sont permis pendant cette seule préparation.
3. Depuis un clone de `main`, lancer `sudo bash install.sh` sur Ubuntu 24.04, ou `sudo bash install.sh --experimental-ubuntu26` sur Ubuntu 26.04. Le script refuse une configuration déjà présente, crée le compte de service, un venv par release, PostgreSQL, les secrets aléatoires et un compte administrateur dont le mot de passe est demandé sans l’afficher.
4. Remplacer le certificat de test par celui de votre PKI LAN. Le nom `doctrad.local` doit être résolu par les clients ; adapter Nginx et les SAN du certificat à votre vrai nom LAN. Installer la confiance PKI sur les postes.
5. Depuis Système & modèles, télécharger explicitement un modèle (voir modeles-telechargement.md), ou transférer les dossiers de modèles dans `/opt/docutranslate/models/translation/`, vérifier les droits et exécuter la commande de vérification sous le compte de service.
6. Ouvrir uniquement HTTPS sur le LAN. PostgreSQL et les deux services FastAPI restent locaux. Ne pas exposer le runtime.
7. Exécuter le diagnostic, tester login/upload/traduction/téléchargement et comparer les références techniques. Puis faire le test isolé complet d’OFFLINE_INSTALL.

Services : `docutranslate-web`, `docutranslate-worker`, `docutranslate-translation`. Configuration : `/etc/docutranslate/docutranslate.env`, mode 640 root:docutranslate ; données : `/var/lib/docutranslate` ; releases : `/opt/docutranslate/releases/0.1.0` et symlink `current`.

Commande administrative : charger l’environnement protégé puis exécuter `/opt/docutranslate/current/.venv/bin/docutranslate` sous le compte `docutranslate`. Ne pas mettre les mots de passe dans les arguments ni dans Git.

L’installateur n’est pas encore transactionnel en cas de panne pendant la création des comptes/DB. Une installation interrompue nécessite un diagnostic avant reprise. Les paquets Ubuntu proviennent des dépôts configurés sur le serveur ; leurs versions ne sont pas figées par le lock Python. Conserver les DEB de validation pour une installation reproductible.

Les téléchargements pip utilisent `/var/tmp/docutranslate-install` plutôt que le tmpfs `/tmp`. Prévoir l’espace nécessaire pour le lock CUDA, une nouvelle release et une sauvegarde ; ne pas confondre mémoire RAM et espace disque.
