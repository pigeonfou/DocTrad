# Installation totalement isolée

Statut : outillage écrit ; bundle complet avec modèles et installation sur machine isolée **non validés**. Aucun bundle utilisable complet n’est livré actuellement.

Sur Ubuntu 24.04 amd64/Python 3.12 connecté, installer `apt-rdepends` et `dpkg-dev`, préparer les modèles, puis :

```bash
./scripts/build-offline-bundle.sh /chemin/nouveau-bundle /chemin/modeles-verifies
```

Le script récupère les wheels verrouillées, les DEB et dépendances récursives, le code et les modèles fournis. Les dépendances virtuelles APT non résolues font échouer la préparation : choisir explicitement leur fournisseur, puis compléter le script et refaire les contrôles. Ne jamais ignorer silencieusement une dépendance. Tester sur une installation Ubuntu vierge pour vérifier la fermeture de toutes les dépendances et l’absence d’incompatibilité avec l’image de base.

Authentifier `MANIFEST.json` sur un canal de confiance. Les SHA256 ne prouvent pas l’origine. Transférer le dossier entier, puis :

```bash
sudo /media/bundle/app/install.sh --offline /media/bundle
```

APT utilise uniquement la liste `file:` temporaire ; pip utilise `--no-index --find-links`. Aucun service ne prépare ni ne télécharge de poids. Les modèles sont contrôlés avant sélection.

Test d’acceptation encore requis : couper l’accès Internet du serveur, redémarrer Ubuntu, vérifier les services, connexion depuis un poste LAN, upload PDF natif puis scan, OCR, vraie traduction locale, DOCX/PDF, téléchargement. Surveiller les tentatives réseau du compte de service avec les outils réseau du serveur. Préserver SSH et le retour HTTPS LAN. Les tests unitaires bloquent les connexions non loopback, mais cela ne constitue pas ce test de redémarrage isolé.
