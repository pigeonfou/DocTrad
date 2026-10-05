# Modèles locaux

Candidats implémentés : OPUS-MT EN→FR (`opus`), M2M100 418M (`m2m100`), MADLAD-400 3B (`madlad`). Aucun modèle entraîné n’a pu être installé : la connexion directe au dépôt de poids a expiré.

Préparation explicite, sur une machine connectée disposant du venv de traduction :

```bash
.venv/bin/python scripts/prepare-model.py opus-mt-en-fr --revision SHA_COMPLET_40_CARACTERES --output /chemin/modeles
```

La révision doit être copiée du dépôt officiel, jamais remplacée par `main`. Le script vérifie la licence annoncée par cette révision, télécharge les fichiers, convertit au besoin les poids officiels PyTorch vers Safetensors avec chargement `weights_only=True`, écrit un manifest et calcule les SHA256. L’inférence de production n’accepte que les poids locaux Safetensors et `trust_remote_code=False`. La conversion est implémentée mais non exécutée sur un checkpoint réel ici.

Transférer chaque dossier dans `MODEL_ROOT`. Commandes : `docutranslate model list`, `info ID`, `verify ID`, `enable ID`, `disable ID`, `set-default ID`, `benchmark ID`. Charger d’abord l’environnement `/etc/docutranslate/docutranslate.env` selon ADMIN_GUIDE.

Sélection : seuls les modèles présents, vérifiés, activés et à licence permissive connue sont éligibles. Le besoin RAM annoncé doit rester sous 85 % de la RAM disponible. Le mode automatique utilise le défaut configuré puis les résultats techniques mesurés et la consommation annoncée. Ce n’est pas encore un ordonnanceur complet tenant compte de la taille document et de la VRAM libre.

Les profils `light`, `balanced`, `quality` sont configurables dans le manifest. Ils ne constituent pas une preuve de qualité. Ne pas choisir automatiquement MADLAD parce qu’il est plus gros. Le manifest conserve source, SHA exact, licence, politique d’usage, CPU/GPU, précision, besoin RAM indicatif, taille disque et benchmark.

NLLB est exclu du registre professionnel. TranslateGemma 4B et Hunyuan-MT-7B ont aussi été recherchés ; ils nécessitent une analyse de leurs licences spécifiques et des adaptateurs distincts. Ils ne sont pas activés ni évalués. Voir LICENSES.
