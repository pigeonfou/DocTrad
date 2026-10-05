# Sécurité

Implémenté : Argon2id, sessions signées HttpOnly/SameSite strict et Secure en production, secret distinct pour le runtime, CSRF sur les mutations, limitation de tentatives de login par IP en mémoire, échappement Jinja, CSP locale, contrôles propriétaire, noms de stockage UUID, limites upload et archives décompressées, refus macros/ActiveX, pas d’exécution de macros, aucune API cloud/CDN.

Limiter Nginx au réseau autorisé. Le certificat de test ne doit pas être considéré comme une PKI de production. Le worker et le runtime ne doivent pas tourner en root. Les services incluent `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`, `ProtectHome`, `ReadWritePaths`, `UMask`. Ces protections n’ont pas été testées via un démarrage systemd dans cet environnement.

Les variables Hugging Face offline sont imposées avant import ; les poids locaux sont obligatoires et le code distant est interdit. Les tests bloquent les connexions Python non loopback. Un contrôle réseau OS reste requis pour prouver l’absence de tentative sortante par les sous-processus/bibliothèques.

Pour une politique de filtrage par UID, réserver une chaîne nftables pour le compte `docutranslate`, autoriser loopback et les réponses aux connexions LAN entrantes, puis refuser les autres connexions initiées par ce compte. Tester d’abord en console locale ; ne jamais filtrer SSH ou remplacer les règles générales du serveur. Aucun filtre global n’est appliqué automatiquement par l’application.

Risques à traiter avant production : erreurs de parseurs sur documents hostiles, bornes mémoire/temps globales par job, limite HTTP avant parsing multipart hors Nginx, attaques ZIP/XML plus fines, administration de sessions persistante, dépendances/audit CVE, rétention et effacement, tests PostgreSQL concurrents et durcissement CPU/GPU. La validation Office ne constitue pas un antivirus.

Les logs de traitement donnent ID de job et type d’erreur sans texte du document. Les uploads/exports et sauvegardes sont confidentiels ; utiliser stockage et transfert chiffrés selon votre politique locale. Le script de restauration est réservé à un backup authentifié ; ne jamais lui fournir une archive non fiable.
