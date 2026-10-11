# IA distante sur le réseau privé

## TranslateGemma 12B Q4_K_M

Dans Unsloth, charger `translategemma-12b-it.Q4_K_M.gguf` depuis
`mradermacher/translategemma-12b-it-GGUF`, avec un contexte de 4096 tokens
pour commencer et une seule traduction à la fois. Décharger Qwen avant.
DocTrad utilise une consigne en texte simple validée avec Unsloth : anglais vers français, température 0 et 1024 tokens de sortie maximum. Les langues
sont également transmises via `chat_template_kwargs` pour llama.cpp.
Le template TranslateGemma du GGUF doit être pris en charge par Unsloth/llama.cpp.
Les requêtes des autres modèles conservent leur prompt générique.

Après déploiement, pour conserver la clé actuelle :

```bash
sudo python3 /opt/oneforall/apps/doctrad/current/scripts/configure-remote-ai.py --translategemma --reuse-key
sudo systemctl restart oneforall-doctrad-runtime oneforall-doctrad-web
```

Le script détecte l'identifiant API réel du modèle chargé et sa quantification,
teste une courte traduction puis affiche le résultat à vérifier en français.
Il active ce moteur par défaut pour les nouveaux travaux. En cas de modèle
absent, de quantification incorrecte ou de réponse invalide, il garde la
configuration précédente. Retirer `--reuse-key` pour saisir une nouvelle clé.
Le test exige une réponse française attendue pour sa phrase de contrôle ;
cela ne garantit pas la qualité linguistique des documents : vérifier le résultat
affiché et comparer ensuite quelques documents représentatifs.
Ne pas changer de modèle pendant des travaux en cours.

Le moteur facultatif remote-bc250 envoie les passages anglais au serveur Unsloth
configuré. L'extraction, l'OCR, les images et l'export restent sur DocTrad.
Il ne faut pas exposer le port Unsloth via Cloudflare.

Après déploiement OneForAll :

```bash
sudo python3 /opt/oneforall/apps/doctrad/current/scripts/configure-remote-ai.py
sudo systemctl restart oneforall-doctrad-runtime oneforall-doctrad-web
```

Saisir la clé uniquement dans l'invite masquée. La configuration et la clé sont
conservées dans /var/lib/oneforall/doctrad, avec accès privé à ofa-doctrad.
Les sauvegardes OneForAll de ce dossier contiennent aussi la clé et doivent rester privées.
Dans les nouveaux documents, sélectionner « BC-250 » ; le bouton administrateur
« Utiliser par défaut » permet de l'utiliser pour le choix automatique.

La configuration remote-ai.json contient enabled, default, base_url, model et
key_file. Le moteur accepte uniquement une IP privée RFC1918 ou de boucle locale,
avec un chemin /v1. Les mandataires d'environnement et redirections sont refusés.
HTTP reste non chiffré sur le LAN ; utiliser HTTPS avec certificat valide si le
réseau n'est pas de confiance.

La révision enregistrée dans un travail identifie l'adresse et le nom du modèle,
pas une empreinte des poids distants. Ne pas remplacer les poids sous le même nom
pendant une traduction. Les réponses tronquées, vides et erreurs sont refusées ;
aucun remplacement silencieux par un modèle local n'est effectué.
Seul choices[0].message.content est exporté, jamais reasoning_content.

Pour désactiver, mettre enabled à false dans remote-ai.json et sélectionner un
modèle local. Aucun changement d'OneForAll, de CablePlan ou d'OddWorks n'est requis.

### Chargement automatique dans Unsloth

Dans **Système & modèles IA → Serveur IA BC-250**, le chargement automatique
sélectionne TranslateGemma 12B Q4_K_M. Le champ **Contexte (tokens)** est
configurable entre 1024 et 32768, avec 4096 par défaut. Le modèle GGUF doit déjà
être présent sur la BC-250. Un contexte plus grand demande davantage de mémoire.

Au début d'une traduction distante, DocTrad appelle, avec la clé privée :
`GET /api/inference/status`, `POST /api/inference/images/unload`, puis si
nécessaire `POST /api/inference/unload` et `POST /api/inference/load` avec
`model_path`, `gguf_variant=Q4_K_M` et `max_seq_length`. L'état final doit confirmer
la quantification et le contexte effectif. Une génération active peut être
interrompue par le déchargement. Le modèle reste chargé après le travail.

Un verrou sur DocTrad réserve la BC-250 pendant chaque document. Le moteur
revérifie aussi les réglages avant les requêtes de traduction. Un changement
externe dans Unsloth peut donc déclencher un nouveau chargement. Le verrou ne
réserve pas la machine aux utilisateurs directs d'Unsloth : ne pas lancer une
génération d'image pendant une traduction.

Ces appels nécessitent une version d'Unsloth exposant ces routes et une clé
autorisée à contrôler les modèles. Un refus 401/403 arrête le travail sans tenter
une connexion anonyme. Les erreurs de chargement et les contextes non respectés
sont signalés ; aucun autre modèle n'est utilisé silencieusement.

Le contexte et le chargement automatique font partie de la révision du modèle.
Après modification des réglages, créer une nouvelle traduction. Décocher le
chargement automatique conserve le fonctionnement manuel du modèle configuré.
