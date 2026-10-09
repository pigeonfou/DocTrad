# DocTrad — intégration, déploiement GitHub Actions et accès Cloudflare

Procédure pour un **Ubuntu Server 24.04 ou 26.04 x86_64 dédié**. Ne pas appliquer telle quelle au serveur Apache/ProjectFlow existant. Prévoir 16 Go RAM minimum et un SSD d'au moins 80 Go libres : le lock Python actuel inclut des bibliothèques CUDA volumineuses et chaque release possède un venv. Aucun conteneur de production.

## À quel moment installe-t-on le runner ?

**Le runner s'installe à l'étape 8**, après l'installation de DocTrad et la préparation du déploiement. Cette étape décrit séparément le téléchargement, l'enregistrement auprès de GitHub et le démarrage permanent du runner.

| Étape | Où agir ? | Ce que vous faites |
|---|---|---|
| 2 | Site GitHub | Préparer les droits du dépôt |
| 3 et 4 | Serveur Ubuntu, puis site GitHub | Préparer Ubuntu et autoriser le serveur à lire DocTrad |
| 5 et 6 | Serveur Ubuntu | Installer l'application et son accès local |
| 7 | Serveur Ubuntu | Préparer le compte et le script de déploiement ; le runner n'est pas encore installé |
| **8** | **Site GitHub et serveur Ubuntu** | **Installer, enregistrer et démarrer le runner** |
| 9 et 10 | Serveur Ubuntu et site Cloudflare | Donner une adresse HTTPS publique au site |

### Pourquoi une clé SSH alors que le runner n'en demande pas ?

**GitHub Actions n'exige pas de clé SSH pour enregistrer le runner.** GitHub fournit un jeton temporaire à cette fin. La clé SSH de l'étape 4 sert à une autre opération : notre script de déploiement récupère lui-même le code du dépôt privé, indépendamment du runner. Le script DocTrad actuel utilise cette clé ; supprimer cette étape sans modifier le script empêcherait les déploiements.

Un workflow peut aussi télécharger le code avec le jeton automatique GitHub, sans clé SSH. L'absence de clé dans votre installation ProjectFlow est donc possible ; ce guide ne suppose pas que ProjectFlow utilise le même mécanisme que DocTrad.

Vous ne devez exporter aucune clé privée. À l'étape 4, vous copiez seulement le texte de la **clé publique** dans GitHub, une seule fois.

## 1. Fonctionnement et limites

GitHub app connecté à ChatGPT → commit sur main → `DocTrad checks` sur runner hébergé GitHub → succès → `DocTrad deploy` sur runner du serveur → sauvegarde, déploiement exact du SHA testé, healthcheck. Le navigateur rejoint le site par Cloudflare Tunnel → Nginx local 8082 → FastAPI 8090. PostgreSQL et runtime 8091 ne sont pas exposés.

Le serveur d'intégration est connecté à Internet. Les modèles IA ne deviennent pas des API distantes, mais les documents servis par le domaine public transitent par Cloudflare. Utiliser des données fictives pour cette phase. Une production réellement isolée impose de désactiver runner/tunnel et de revenir à une installation LAN/offline.

Les fichiers livrés ont été contrôlés syntaxiquement ; le déploiement et le tunnel devront être validés sur votre serveur. La V1 de traduction demeure partielle : installer les modèles et terminer les tests d'acceptation avant usage réel.

## 2. GitHub : dépôt privé et droits

Dans `pigeonfou/DocTrad`, Settings → General → Danger Zone → Change repository visibility → Private. Vérifier que le connecteur GitHub de ChatGPT garde accès à DocTrad. Le workflow de déploiement refuse les événements provenant d'un dépôt public. Conserver les tests des pull requests sur runners hébergés GitHub ; ne jamais affecter une PR externe au runner du serveur.

GitHub recommande les runners auto-hébergés sur des dépôts privés : https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners

N'autoriser l'écriture qu'aux personnes et applications auxquelles vous faites confiance. Un auteur de code déployé peut agir avec les droits du compte applicatif. Ne pas imposer une approbation manuelle à chaque déploiement si l'objectif est l'autonomie ; les tests et le filtrage main restent obligatoires.

## 3. Ubuntu : prérequis

Sur le serveur, avec votre compte administrateur sudo :

```bash
sudo apt-get update
sudo apt-get install -y git curl ca-certificates openssh-client python3 python3-venv sudo
lsb_release -a
uname -m
free -h
df -h /
```

Ne pas installer Apache ni Docker. Sorties HTTPS vers GitHub/PyPI pendant les installations ; pour cloudflared, autoriser le trafic sortant requis, notamment le port 7844 TCP/UDP. Aucun port entrant Internet, aucune redirection de la box ne sont nécessaires au tunnel. Préserver votre accès SSH existant.

## 4. Clé SSH de lecture du dépôt privé

Cette clé est uniquement sur le serveur, ne permet pas de pousser et ne doit pas être envoyée dans ChatGPT.

```bash
sudo install -d -m 700 /root/.ssh
sudo ssh-keygen -t ed25519 -f /root/.ssh/doctrad-deploy-ed25519 -N '' -C 'doctrad-server-read-only'
sudo cat /root/.ssh/doctrad-deploy-ed25519.pub
```

Copier **uniquement la clé .pub** dans GitHub → DocTrad → Settings → Deploy keys → Add deploy key. Nom : `Ubuntu DocTrad — lecture`. Laisser **Allow write access décoché**.

La lecture Git utilise SSH vers `ssh.github.com` sur le port sortant 443 ; pas besoin d'ouvrir le port entrant SSH ni le port sortant 22. Récupérer les clés d'hôte GitHub par l'API HTTPS officielle, sans accepter aveuglément une clé SSH proposée :

```bash
curl -fsSL https://api.github.com/meta \
  | python3 -c 'import json,sys; print("\n".join("github.com,[ssh.github.com]:443 " + key for key in json.load(sys.stdin)["ssh_keys"]))' \
  | sudo tee -a /root/.ssh/known_hosts >/dev/null
sudo chmod 600 /root/.ssh/known_hosts
```

Cloner la source :

```bash
sudo install -d -m 755 /usr/local/src
sudo git -c core.sshCommand='ssh -p 443 -o HostName=ssh.github.com -i /root/.ssh/doctrad-deploy-ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes' \
  clone git@github.com:pigeonfou/DocTrad.git /usr/local/src/DocTrad
```

Si ces chemins existent déjà, inspecter leur contenu ; ne pas régénérer/écraser une clé ni recloner sur une installation existante.

## 5. Première installation native

```bash
cd /usr/local/src/DocTrad
sudo bash install.sh
# Ubuntu 26.04 : utiliser à la place sudo bash install.sh --experimental-ubuntu26
```

Le script demande le nom et le mot de passe administrateur (12 caractères minimum), génère les secrets, crée les services natifs et la DB. Plusieurs gigaoctets seront téléchargés. Aucun modèle n'est téléchargé implicitement.

Vérifier :

```bash
sudo systemctl status docutranslate-web docutranslate-worker docutranslate-translation --no-pager
curl -fsS http://127.0.0.1:8090/health
```

Un HTTP 200 signifie que le socle web/DB fonctionne ; `ready=false` et `local_models=0` signifient qu'il manque encore le moteur de traduction. Ne pas relancer install.sh sur une configuration partielle sans diagnostic.

## 6. Nginx réservé au tunnel

Sur ce serveur dédié, remplacer uniquement le site DocTrad et retirer le site de démonstration Nginx :

```bash
sudo install -m 644 /usr/local/src/DocTrad/packaging/nginx/docutranslate-tunnel.conf /etc/nginx/sites-available/docutranslate
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
curl -fsS http://127.0.0.1:8082/health
```

Le site écoute uniquement `127.0.0.1:8082`. HTTP est utilisé pour le saut sur la même machine ; HTTPS public sera assuré par Cloudflare. Le proxy transmet `X-Forwarded-Proto: https` et les cookies Secure de l'application restent activés. Il n'y a aucune redirection locale susceptible de former une boucle.

## 7. Préparer le déploiement — le runner sera installé à l'étape suivante

```bash
sudo /usr/local/src/DocTrad/scripts/setup-github-deployment.sh
sudo visudo -cf /etc/sudoers.d/docutranslate-deploy
```

Cela crée `docutranslate-runner`, une copie Git bare root à origine fixe, le wrapper root `/usr/local/sbin/docutranslate-deploy` et son autorisation sudo spécifique. Le runner n'obtient pas `sudo ALL` et ne rejoint pas le groupe qui lit les secrets applicatifs.

Le wrapper ne lit pas le checkout modifiable du runner : il récupère lui-même le dépôt fixe par clé SSH de lecture et vérifie le SHA exact de main. Les builds Python s'exécutent sous `docutranslate`, jamais root. Les backups restent sous `/var/backups/docutranslate` avec accès root.

## 8. Installer le runner GitHub Actions sur Ubuntu

Un runner est le petit programme installé sur votre serveur qui reçoit les tâches de GitHub Actions. L'étape 7 a créé son compte Linux ; elle n'a pas téléchargé ce programme.

### 8A. Sur le site GitHub : afficher les commandes d'installation

1. Ouvrir [les réglages des runners DocTrad](https://github.com/pigeonfou/DocTrad/settings/actions/runners).
2. Cliquer sur **New self-hosted runner**.
3. Sélectionner **Linux**, puis **x64**.
4. Garder cette page ouverte. Elle affiche deux parties : **Download** et **Configure**.

### 8B. Sur le serveur Ubuntu : télécharger et installer le programme

Depuis votre compte Ubuntu habituel, exécuter :

```bash
sudo -iu docutranslate-runner
mkdir -p ~/actions-runner
cd ~/actions-runner
```

Vous êtes maintenant dans le compte réservé au runner et dans son dossier d'installation.

Dans la partie **Download** de la page GitHub, copier et exécuter, une par une, les commandes qui :

1. téléchargent l'archive (commande `curl`) ;
2. vérifient sa somme de contrôle, si la commande est proposée ;
3. extraient l'archive (commande `tar`).

**Ne pas recopier la commande GitHub qui crée le dossier et entre dedans** : nous venons de le faire. Les commandes de téléchargement et d'extraction s'exécutent ici **sans sudo**. Leur version est celle affichée par GitHub ; aucun numéro de version ancien n'est à recopier depuis ce guide.

Vérifier que le téléchargement et l'extraction ont réussi :

```bash
ls config.sh svc.sh
```

Résultat attendu : les deux fichiers apparaissent. En cas d'erreur, ne pas continuer avant de la résoudre.

### 8C. Sur le serveur Ubuntu : associer le runner à DocTrad

La partie **Configure** de GitHub affiche une commande `./config.sh` contenant un jeton. Copier ce jeton dans la commande ci-dessous, à la place de `JETON_TEMPORAIRE_GITHUB`, puis exécuter :

```bash
./config.sh --url https://github.com/pigeonfou/DocTrad --token JETON_TEMPORAIRE_GITHUB --name doctrad-ubuntu --labels doctrad-deploy --unattended
```

Le nom est `doctrad-ubuntu` et le label doit être exactement `doctrad-deploy` : notre workflow recherche ce label. Ce runner est associé à DocTrad, séparément de ProjectFlow.

Le jeton sert uniquement à l'enregistrement et expire après une heure. Si GitHub indique qu'il a expiré, rouvrir la page **New self-hosted runner** et utiliser le nouveau jeton. Ne pas envoyer ce jeton dans ChatGPT ni le publier dans Git.

Une fois l'enregistrement réussi, revenir à votre compte Ubuntu habituel :

```bash
exit
```

### 8D. Sur le serveur Ubuntu : démarrer le runner comme service permanent

Copier ce bloc complet depuis votre compte Ubuntu habituel :

```bash
sudo bash <<'ROOT'
cd /home/docutranslate-runner/actions-runner
./svc.sh install docutranslate-runner
./svc.sh start
./svc.sh status
ROOT
```

Le service est maintenant installé et démarré. Il redémarrera automatiquement avec Ubuntu. **Ne pas lancer en plus `./run.sh`**, proposé sur la page GitHub : nous utilisons le service permanent à sa place.

### 8E. Sur le site GitHub : vérifier que l'installation est terminée

Retourner dans **Settings → Actions → Runners** et actualiser la page.

Résultat attendu : **doctrad-ubuntu — Idle**, avec le label **doctrad-deploy**. Idle signifie « connecté et disponible » ; Offline signifie « non connecté ». Si le runner est Offline, vérifier le résultat de `./svc.sh status` avant de passer à Cloudflare.

Il n'y a pas de fichier workflow à créer : le workflow de tests et `.github/workflows/deploy.yml` sont déjà livrés dans le dépôt. Après un nouveau push sur `main`, les tests passent d'abord sur GitHub ; s'ils réussissent et que le dépôt est privé, le runner de votre serveur reçoit le déploiement. L'installation du runner ne déclenche pas à elle seule un déploiement.

Documentation officielle : https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners

## 9. Cloudflare : installer cloudflared

Dépôt officiel : https://pkg.cloudflare.com/

```bash
sudo install -d -m 755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update
sudo apt-get install -y cloudflared
cloudflared --version
```

## 10. Cloudflare : tunnel permanent et domaine

Dans Cloudflare, sélectionner le compte contenant votre domaine actif. Aller à **Networking → Tunnels**, créer un tunnel Cloudflared nommé `doctrad-ubuntu` et choisir Debian/Ubuntu. Selon l'interface de votre compte, ce parcours peut encore apparaître dans Zero Trust → Networks → Tunnels.

Exécuter sur le serveur **la commande d'installation du service fournie par Cloudflare**, de la forme :

```bash
sudo cloudflared service install JETON_DU_TUNNEL
sudo systemctl enable --now cloudflared
sudo systemctl show cloudflared -p ActiveState -p SubState
```

Ne pas copier le jeton ici ni le mettre dans GitHub. Éviter de partager un `systemctl status cloudflared` complet : la ligne de commande du service peut contenir le jeton. La commande `systemctl show` ci-dessous affiche uniquement son état. Si un service cloudflared existe déjà sur ce serveur, ajouter la route à son tunnel plutôt que tenter une seconde installation du même service.

Dans le tunnel, **Routes → Add route → Published application** :

| Champ | Valeur |
|---|---|
| Subdomain | `doctrad` |
| Domain | votre domaine actif |
| Path | vide |
| Service type | HTTP |
| Service URL | `127.0.0.1:8082` |

L'URL finale est `https://doctrad.VOTRE-DOMAINE`. Cloudflare crée normalement le CNAME vers `<UUID>.cfargotunnel.com`. En cas de conflit DNS sur ce sous-domaine, vérifier puis supprimer seulement l'ancien enregistrement concerné. Aucun enregistrement A vers votre IP publique n'est nécessaire.

Dans le domaine Cloudflare, créer aussi une **Redirect Rule / Single Redirect** limitée à DocTrad pour forcer HTTPS :

- Condition personnalisée : `(http.host eq "doctrad.VOTRE-DOMAINE" and http.request.scheme eq "http")`, en remplaçant le domaine.
- Redirection dynamique : `concat("https://", http.host, http.request.uri.path)`.
- Code : **301** ; **Preserve query string** activé.

Vérifier que `http://doctrad.VOTRE-DOMAINE/login` redirige vers HTTPS. Si tous les sites du domaine utilisent déjà HTTPS, **SSL/TLS → Edge Certificates → Always Use HTTPS** est une alternative globale ; la règle ci-dessus conserve un périmètre limité à DocTrad.

Conserver HTTPS public et les protections de connexion de DocTrad. Ne pas mettre une règle Cache Everything sur ce sous-domaine. Les longues traductions sont asynchrones : elles ne nécessitent pas un proxy HTTP bloqué pendant leur durée.

Documentation : https://developers.cloudflare.com/tunnel/get-started/ et https://developers.cloudflare.com/tunnel/troubleshooting/https-origins/

## 11. Vérifications et informations à fournir

```bash
sudo /usr/local/sbin/docutranslate-deploy --status
sudo systemctl show cloudflared -p ActiveState -p SubState
```

Depuis un poste hors du LAN, visiter `https://doctrad.VOTRE-DOMAINE/login` et vérifier la page de connexion. S'authentifier avec le compte de test. Cloudflare Access peut être ajouté, mais une première authentification Access devra alors aussi être effectuée dans le navigateur partagé ; ne pas considérer son activation comme une connexion automatique de ChatGPT.

Fournir à ChatGPT : URL publique exacte, confirmation runner Idle et résultats d'état sans secrets. Pour permettre les tests web, authentifier le navigateur partagé lorsqu'il est ouvert ; ne pas publier les mots de passe ou jetons dans Git. Je peux réutiliser une session tant qu'elle reste valide, mais une expiration de connexion peut demander une intervention.

Je pourrai ensuite pousser un changement de test, suivre `DocTrad checks` puis `DocTrad deploy`, examiner les logs et vérifier le site après authentification. Il n'est pas nécessaire de me donner un accès SSH public ni un mot de passe root. La première mise en place exige vos actions sur le serveur/GitHub/Cloudflare ; les déploiements suivants sont automatisés pendant nos travaux. ChatGPT ne fonctionne pas en continu hors d'une session ou d'une automatisation explicitement configurée.

## 12. Après installation et récupération

Modèles : suivre MODELS.md, préparer des poids sur la machine connectée, vérifier et transférer dans MODEL_ROOT. Ne pas confondre déploiement du site et validation d'une vraie traduction.

Chaque commit testé crée `/opt/docutranslate/releases/<SHA>` ; `current` bascule atomiquement. En cas d'échec après arrêt des services, le wrapper restaure la DB sauvegardée et l'ancien code. Une panne électrique/kill brutal reste un cas de récupération manuelle. Ne pas supprimer des releases/backups actifs ; définir une rétention après validation. Les unités systemd/Nginx et le wrapper root ne sont pas automatiquement remplacés par du code du dépôt : leurs évolutions nécessitent une installation administrateur explicite.

Retour au code précédent, **seulement si le schéma reste compatible** :

```bash
sudo /usr/local/sbin/docutranslate-deploy --rollback
```

Sinon restaurer le backup selon BACKUP_RESTORE.md. Les déploiements redémarrent les services ; éviter de lancer des traductions longues pendant cette phase d'intégration. Les jobs interrompus peuvent nécessiter la récupération décrite dans ADMIN_GUIDE.md.

Diagnostic :

```bash
sudo /usr/local/sbin/docutranslate-deploy --logs
sudo journalctl -u cloudflared -n 80 --no-pager
curl -fsS http://127.0.0.1:8090/health
curl -fsS http://127.0.0.1:8082/health
```

8090 en panne : application/DB/services ; 8082 en panne avec 8090 OK : Nginx ; local OK mais public en panne : tunnel/route/DNS/Cloudflare Access. Ne pas désactiver l'authentification pour résoudre ces erreurs.

## Installation gérée par OneForAll

Cette chaîne autonome cible `/opt/docutranslate` et les services `docutranslate-*`. Pour l’instance `/opt/oneforall/apps/doctrad`, suivre [ONEFORALL.md](ONEFORALL.md) et le runner OneForAll ; ne pas installer le runner autonome sur cette même instance. Le téléchargement initial de modèles est désormais accessible depuis Système & modèles ; la traduction reste locale.
