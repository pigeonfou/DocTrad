# IA distante sur le réseau privé

## TranslateGemma 12B Q4_K_M

Dans Unsloth, charger `translategemma-12b-it.Q4_K_M.gguf` depuis
`mradermacher/translategemma-12b-it-GGUF`, avec un contexte de 4096 tokens
pour commencer et une seule traduction à la fois. Décharger Qwen avant.
DocTrad utilise le contenu typé TranslateGemma : source `en`, cible `fr`,
texte seul, température 0 et 1024 tokens de sortie maximum. Les langues
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
Un test API réussi ne garantit pas la qualité linguistique : vérifier le résultat
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
