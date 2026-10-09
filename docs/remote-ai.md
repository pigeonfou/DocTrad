# IA distante sur le réseau privé

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
