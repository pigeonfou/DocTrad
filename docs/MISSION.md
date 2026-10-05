# MISSION — CONSTRUIRE UN SERVEUR NATIF DE TRADUCTION DOCUMENTAIRE IA 100 % HORS LIGNE

Vous devez concevoir, développer, installer, tester, sécuriser, documenter et préparer au déploiement une application web de traduction automatique de documentation technique de l’anglais vers le français.

L’application cible doit fonctionner sur :

**Ubuntu Server 24.04 LTS x86-64**

Elle doit être accessible depuis les postes du réseau local au moyen d’un navigateur web.

## CONTRAINTE ARCHITECTURALE ABSOLUE

**NE PAS UTILISER DOCKER, PODMAN, LXC OU TOUT AUTRE SYSTÈME DE CONTENEURS POUR LE DÉPLOIEMENT DE PRODUCTION.**

L’application doit être installée nativement sur Ubuntu à l’aide de :

- packages Ubuntu ;
- environnements virtuels Python ;
- services `systemd` ;
- Nginx ;
- PostgreSQL ;
- Redis si nécessaire ;
- répertoires dédiés sous `/opt`, `/etc` et `/var`.

La seconde contrainte fondamentale est :

**UNE FOIS INSTALLÉE, L’APPLICATION DOIT POUVOIR FONCTIONNER NORMALEMENT SANS AUCUN ACCÈS À INTERNET.**

Aucun document, texte, image, métadonnée, télémétrie ou résultat ne doit être envoyé vers un service extérieur.

Tous les modèles IA, modèles OCR, bibliothèques et fichiers nécessaires doivent être présents localement.

---

# 1. OBJECTIF

Construire une première version réellement exploitable d’un :

**SERVEUR LOCAL DE TRADUCTION DOCUMENTAIRE TECHNIQUE ANGLAIS → FRANÇAIS UTILISANT DES MODÈLES IA LOCAUX.**

L’utilisateur doit pouvoir :

1. accéder à l’application par navigateur ;
2. s’authentifier ;
3. déposer un document anglais ;
4. choisir les options de traduction ;
5. choisir éventuellement le moteur IA ;
6. lancer le traitement ;
7. suivre sa progression ;
8. consulter les alertes ;
9. comparer original et traduction ;
10. corriger certains passages ;
11. enrichir un glossaire ;
12. mémoriser les corrections ;
13. télécharger le résultat traduit.

---

# 2. DOCUMENTATIONS CIBLÉES

L’application doit particulièrement convenir aux documents :

- électroniques ;
- électriques ;
- mécaniques ;
- industriels ;
- logiciels ;
- R&D ;
- notices techniques ;
- manuels utilisateur ;
- manuels de maintenance ;
- dossiers de conception ;
- spécifications ;
- procédures ;
- fiches techniques.

La priorité est l’exactitude technique plutôt que la traduction littéraire.

---

# 3. LANGUES

La V1 sera spécialisée dans :

**anglais → français**

Ne pas compliquer inutilement la première version.

L’architecture devra cependant permettre ultérieurement l’ajout d’autres langues.

---

# 4. FORMATS

Support prioritaire :

- PDF texte ;
- PDF scanné ;
- DOCX ;
- PPTX ;
- PNG ;
- JPEG ;
- TIFF si raisonnablement possible.

Prévoir une architecture extensible.

---

# 5. PIPELINE GÉNÉRALE

Construire une chaîne modulaire :

```text
Document
   ↓
Identification du format
   ↓
Analyse documentaire
   ↓
Extraction texte natif
   ↓
OCR si nécessaire
   ↓
Détection structure
   ↓
Segmentation
   ↓
Protection terminologique
   ↓
Glossaire
   ↓
Mémoire de traduction
   ↓
Moteur IA sélectionné
   ↓
Contrôle qualité
   ↓
Post-édition facultative
   ↓
Reconstruction documentaire
   ↓
Validation utilisateur
   ↓
Export PDF / DOCX
```

Chaque module doit pouvoir être remplacé indépendamment.

---

# 6. ARCHITECTURE UBUNTU NATIVE

Privilégier l’architecture :

```text
                         ┌──────────────────┐
LAN ─────── HTTPS ─────►│      NGINX       │
                         └────────┬─────────┘
                                  │
                           127.0.0.1 / socket
                                  │
                         ┌────────▼─────────┐
                         │    FastAPI       │
                         │   Application    │
                         └──────┬───┬───────┘
                                │   │
                  ┌─────────────┘   └────────────┐
                  ▼                              ▼
            PostgreSQL                         Redis
                                                   │
                                                   ▼
                                             Job Worker
                                                   │
                              ┌────────────────────┼────────────────┐
                              ▼                    ▼                ▼
                           Docling             PaddleOCR      Translation
                                                                   │
                                                                   ▼
                                                       Local Model Runtime
```

Tout doit résider sur le même serveur dans la V1.

Ne pas créer de microservices réseau inutiles.

---

# 7. SERVICES SYSTEMD

Créer des services `systemd` propres.

Au minimum :

```text
docutranslate-web.service
docutranslate-worker.service
docutranslate-translation.service
```

Éventuellement :

```text
docutranslate-ocr.service
```

uniquement si cela apporte un véritable bénéfice.

Utiliser les services Ubuntu natifs pour :

```text
nginx
postgresql
redis-server
```

Ne pas encapsuler PostgreSQL ou Redis dans l’application.

---

# 8. IMPORTANT — NE PAS CHARGER LE MODÈLE PLUSIEURS FOIS

Un modèle de plusieurs milliards de paramètres peut utiliser beaucoup de RAM/VRAM.

Ne pas charger une copie du modèle dans chaque worker web.

Créer de préférence un :

**Translation Runtime Service**

chargé une seule fois en mémoire.

Exemple :

```text
Worker
   ↓
127.0.0.1 ou socket Unix
   ↓
Translation Runtime
   ↓
Modèle IA local
```

Ce service doit uniquement être accessible localement.

Il doit pouvoir :

- charger un modèle ;
- décharger un modèle ;
- changer de modèle ;
- rapporter son état ;
- signaler RAM/VRAM utilisée ;
- traiter des segments ;
- effectuer du batch lorsque pertinent.

---

# 9. ENVIRONNEMENTS PYTHON

Ubuntu 24.04 utilise Python système pour certains composants.

**NE JAMAIS INSTALLER LES PACKAGES PYTHON DE L’APPLICATION GLOBALEMENT DANS LE PYTHON SYSTÈME.**

Utiliser des environnements virtuels.

Exemple :

```text
/opt/docutranslate/
├── app/
├── venv/
├── models/
├── data/
├── uploads/
├── outputs/
├── temp/
├── logs/
└── backups/
```

Si les dépendances Docling / Paddle / PyTorch deviennent incompatibles entre elles, utiliser plusieurs environnements :

```text
/opt/docutranslate/venvs/
├── web/
├── worker/
├── translation/
└── ocr/
```

Ne multiplier les environnements que si cela résout un vrai problème de compatibilité.

---

# 10. UTILISATEUR SYSTÈME

Créer un compte de service sans connexion interactive :

```text
docutranslate
```

L’application ne doit jamais tourner en root.

Attribuer uniquement les permissions réellement nécessaires.

---

# 11. EMPLACEMENTS LINUX

Respecter autant que possible cette organisation :

```text
/opt/docutranslate/
    application et environnements Python

/etc/docutranslate/
    configuration

/var/lib/docutranslate/
    données persistantes

/var/log/docutranslate/
    journaux

/var/cache/docutranslate/
    caches contrôlés
```

Les modèles peuvent être placés dans :

```text
/opt/docutranslate/models/
```

ou :

```text
/var/lib/docutranslate/models/
```

Choisir une convention et la conserver.

---

# 12. ANALYSE DOCUMENTAIRE

Utiliser prioritairement **Docling**.

Objectifs :

- reconnaître la structure des PDF ;
- titres ;
- paragraphes ;
- listes ;
- tableaux ;
- images ;
- légendes ;
- ordre de lecture ;
- pages.

Configurer Docling afin qu’il utilise uniquement des modèles présents localement.

Aucun téléchargement automatique ne doit être nécessaire.

---

# 13. OCR

Utiliser prioritairement **PaddleOCR** avec modèles locaux.

Il devra pouvoir traiter :

- PDF scannés ;
- captures ;
- illustrations ;
- schémas ;
- annotations.

Conserver :

```text
texte
page
image
bounding box
coordonnées
confiance OCR
```

Ne jamais télécharger automatiquement des poids manquants.

---

# 14. REGISTRE DE MODÈLES IA

Créer une architecture générique.

Définir une interface du type :

```python
class TranslationEngine:
    def load(...)
    def unload(...)
    def translate(...)
    def translate_batch(...)
    def health(...)
    def capabilities(...)
```

Créer également un **Model Registry**.

Chaque modèle doit avoir des métadonnées telles que :

```text
id
nom
famille
version
révision exacte
chemin local
licence
taille disque
RAM estimée
VRAM estimée
CPU compatible
GPU compatible
quantification
langue source
langue cible
statut
benchmark
date installation
checksum
```

---

# 15. PLUSIEURS MODÈLES DE TRADUCTION

Ne pas verrouiller l’application sur un seul modèle.

Prévoir plusieurs moteurs locaux interchangeables.

Candidats initiaux à examiner et BENCHMARKER :

## A — OPUS-MT EN→FR

Exemple :

```text
Helsinki-NLP/opus-mt-en-fr
```

Utilisation envisagée :

- mode léger ;
- CPU ;
- machines avec peu de RAM ;
- traduction rapide.

---

## B — M2M100 418M

Exemple :

```text
facebook/m2m100_418M
```

Utilisation envisagée :

- modèle intermédiaire ;
- CPU puissant ou GPU ;
- comparaison avec OPUS.

Ne pas supposer qu’il sera meilleur.

Le benchmark décidera.

---

## C — MADLAD-400 3B MT

Exemple :

```text
google/madlad400-3b-mt
```

Utilisation envisagée :

- profil qualité ;
- GPU recommandé ;
- éventuellement CPU puissant si réellement acceptable.

Tester différentes précisions et quantifications.

---

## D — NLLB

Exemple :

```text
facebook/nllb-200-distilled-600M
```

Ce modèle peut être testé à titre comparatif.

ATTENTION :

sa licence peut restreindre certains usages commerciaux.

Il ne doit donc pas devenir automatiquement le moteur par défaut d’un produit professionnel.

Afficher clairement le statut de licence.

---

# 16. RECHERCHER D’AUTRES MODÈLES

Lors de la réalisation du projet, vérifier s’il existe des modèles locaux plus récents ou plus adaptés.

Pour chaque candidat, vérifier :

1. fonctionnement réellement local ;
2. anglais → français ;
3. licence ;
4. utilisation professionnelle ;
5. qualité ;
6. RAM ;
7. VRAM ;
8. vitesse ;
9. maturité ;
10. disponibilité des poids ;
11. fonctionnement hors ligne.

Ne sélectionner aucun modèle simplement parce qu’il est récent.

Comparer avec les références précédentes.

---

# 17. MODÈLES COMMERCIALEMENT COMPATIBLES

Créer dans le registre un champ :

```text
usage_policy
```

avec par exemple :

```text
permissive
restricted
non-commercial
unknown
```

Dans l’interface administrateur, afficher clairement :

```text
✓ Utilisation professionnelle compatible
⚠ Vérification requise
✗ Non destiné à un usage commercial
```

Ne jamais masquer une restriction de licence.

---

# 18. CHOIX DU MOTEUR PAR L’UTILISATEUR

Dans la page de lancement d’une traduction, proposer :

```text
Moteur de traduction :

○ Automatique
○ Rapide
○ Équilibré
○ Qualité maximale
○ Modèle spécifique...
```

Si `Modèle spécifique` est choisi, afficher uniquement les modèles réellement installés.

Exemple :

```text
OPUS-MT EN→FR
M2M100 418M
MADLAD-400 3B
```

---

# 19. MODE AUTOMATIQUE

Créer :

```text
TRANSLATION_PROFILE=auto
```

Le serveur doit examiner :

- CPU ;
- RAM disponible ;
- GPU ;
- VRAM ;
- modèle présent ;
- taille document ;
- file d’attente.

Puis choisir un modèle réellement installé.

Il ne doit JAMAIS télécharger automatiquement le modèle manquant.

---

# 20. PROFILS

Prévoir au minimum :

```text
auto
light
balanced
quality
```

Par exemple, après benchmark :

```text
light
→ OPUS-MT

balanced
→ meilleur modèle intermédiaire réellement mesuré

quality
→ MADLAD-400 3B ou meilleur candidat validé
```

Ces associations doivent rester configurables.

---

# 21. BENCHMARK AUTOMATIQUE

Créer un outil :

```bash
sudo -u docutranslate /opt/docutranslate/bin/benchmark-models
```

Il doit tester chaque moteur installé sur un corpus identique.

Mesurer :

- secondes / segment ;
- mots / seconde ;
- temps/page estimé ;
- RAM maximale ;
- VRAM maximale ;
- conservation des nombres ;
- conservation des unités ;
- respect glossaire ;
- qualité de traduction.

Si possible calculer :

- BLEU ;
- chrF ;
- COMET ou métrique pertinente utilisable localement.

Ne pas utiliser uniquement une métrique automatique.

Créer également un petit corpus de validation technique EN/FR.

---

# 22. SCORE TECHNIQUE

Le classement du meilleur moteur ne doit pas seulement dépendre du français produit.

Donner beaucoup de poids à :

- nombres ;
- références ;
- unités ;
- noms de composants ;
- acronymes ;
- termes du glossaire.

Une traduction fluide qui modifie :

```text
J3
12 VDC
STM32F407
4.5 Nm
```

doit être considérée comme mauvaise.

---

# 23. POST-ÉDITION PAR LLM — OPTIONNELLE

Prévoir architecturalement un second moteur facultatif :

```text
PostEditingEngine
```

Il pourra ultérieurement utiliser un petit LLM local pour :

- améliorer le français ;
- harmoniser le style ;
- corriger certaines formulations.

Mais :

**le LLM de post-édition ne doit jamais être obligatoire.**

La traduction spécialisée reste le moteur principal.

Avant/après post-édition, vérifier automatiquement :

- nombres ;
- unités ;
- références ;
- noms protégés.

Le LLM n’a pas le droit de les modifier.

---

# 24. CHOIX D’UN LLM LOCAL

Si une post-édition LLM est implémentée :

NE PAS choisir arbitrairement un modèle dans ce prompt.

ChatGPT Work doit examiner les modèles locaux actuels disponibles au moment du développement et comparer :

- licence ;
- français ;
- RAM ;
- VRAM ;
- vitesse ;
- quantification ;
- exécution CPU ;
- exécution GPU.

Créer une interface permettant de changer ultérieurement le LLM sans modifier le reste de l’application.

---

# 25. GLOSSAIRE

Créer une base locale permettant par exemple :

```text
housing → boîtier
connector → connecteur
harness → faisceau
fixture → outillage
power supply → alimentation
torque → couple
```

Chaque entrée :

```text
source
target
catégorie
priorité
commentaire
actif
```

Supporter les expressions composées de plusieurs mots.

---

# 26. TERMES PROTÉGÉS

Créer un mécanisme robuste de placeholders.

Protéger notamment :

```text
STM32F407
J3
R27
USB-C
CAN
RS-485
12 VDC
24 V
4.5 Nm
M4x20
ISO 9001
RoHS
REACH
```

Pipeline :

```text
texte source
→ détection références
→ placeholders
→ traduction
→ réinjection
→ contrôle
```

Ne pas laisser uniquement le modèle IA décider.

---

# 27. CONTRÔLE DES NOMBRES

Comparer automatiquement source et traduction.

Signaler :

- nombre disparu ;
- nombre ajouté ;
- décimale modifiée ;
- signe modifié ;
- unité modifiée ;
- référence modifiée.

Prévoir des exceptions configurables.

---

# 28. MÉMOIRE DE TRADUCTION

Créer une mémoire locale :

```text
segment source
→ traduction validée
```

Lorsqu’un segment identique revient :

- utiliser en priorité la traduction validée ;
- éviter un nouvel appel au modèle.

Prévoir une architecture future pour les correspondances approximatives.

---

# 29. VERSIONNER LES CORRECTIONS

Conserver :

```text
traduction IA
traduction corrigée
utilisateur
date
moteur IA
version modèle
```

Cela permettra d’analyser les performances des moteurs.

---

# 30. SEGMENTATION

Respecter :

- phrases ;
- paragraphes ;
- listes ;
- titres ;
- cellules ;
- légendes.

Ne pas traduire un PDF entier en une seule requête.

Ne pas non plus découper excessivement le texte au point de perdre son contexte.

---

# 31. TABLEAUX

Conserver :

- lignes ;
- colonnes ;
- cellules ;
- valeurs numériques ;
- unités.

Traduire uniquement le contenu textuel pertinent.

---

# 32. IMAGES SANS TEXTE

Les conserver inchangées.

---

# 33. TEXTE DANS LES IMAGES

Créer un mode :

```text
Traduire les annotations dans les images
```

Pipeline :

```text
image
→ OCR
→ bounding boxes
→ traduction
→ masque
→ inpainting / reconstruction
→ texte français
→ contrôle
```

Utiliser selon besoin :

- PaddleOCR ;
- OpenCV ;
- Pillow.

Conserver systématiquement l’image originale.

---

# 34. OCR INCERTAIN

En dessous d’un seuil configurable :

NE PAS écraser silencieusement l’original.

Signaler :

```text
Texte détecté avec faible confiance — vérification nécessaire.
```

---

# 35. RECONSTRUCTION

Conserver prioritairement :

1. ordre des pages ;
2. structure ;
3. titres ;
4. paragraphes ;
5. tableaux ;
6. images ;
7. légendes ;
8. références.

Ne pas chercher inutilement une reproduction pixel-perfect lorsque le format ne le permet pas.

---

# 36. EXPORT

Au minimum :

```text
DOCX
PDF
```

Optionnellement :

```text
PDF bilingue
rapport de traduction
texte structuré
```

---

# 37. CONVERSION PDF

Évaluer les méthodes disponibles.

LibreOffice headless peut être utilisé localement lorsqu’il apporte un avantage réel pour :

```text
DOCX → PDF
PPTX → PDF
```

Mais tester le résultat.

Ne pas rendre LibreOffice obligatoire si une solution Python est plus robuste pour un cas donné.

---

# 38. INTERFACE

Créer une interface professionnelle mais simple.

Technologie privilégiée :

```text
FastAPI
Jinja2
HTML
CSS
JavaScript léger
HTMX local si utile
```

Éviter une SPA complexe sans bénéfice.

---

# 39. AUCUN CDN

Interdit :

```text
Google Fonts
cdnjs
jsDelivr
unpkg
Bootstrap CDN
scripts distants
assets distants
```

Tous les fichiers nécessaires doivent être présents localement.

---

# 40. FILE DE TRAVAUX

Les documents peuvent prendre plusieurs minutes.

Ne pas maintenir une requête HTTP ouverte.

Utiliser une file de jobs.

Redis + Celery constitue une solution acceptable.

Une alternative plus simple peut être retenue si elle est robuste.

---

# 41. CONCURRENCE

Ne pas lancer simultanément plusieurs jobs GPU lourds simplement parce qu’il y a plusieurs workers.

Créer une gestion des ressources.

Exemple :

```text
CPU jobs : plusieurs possibles
GPU translation : 1 job ou batch contrôlé
OCR GPU : concurrence limitée
```

La configuration doit être réglable.

---

# 42. POSTGRESQL

Installer PostgreSQL nativement depuis les dépôts Ubuntu ou source validée.

L’utiliser pour :

- comptes ;
- documents ;
- jobs ;
- glossaire ;
- mémoire ;
- paramètres ;
- alertes ;
- historique.

Utiliser Alembic ou équivalent pour les migrations.

---

# 43. REDIS

Installer Redis nativement si utilisé.

Le limiter à localhost.

Configurer correctement persistance et sécurité selon son rôle.

---

# 44. NGINX

Nginx doit être le seul composant exposé au LAN.

Le serveur FastAPI doit écouter :

```text
127.0.0.1
```

ou utiliser un socket Unix.

Nginx assure :

- reverse proxy ;
- HTTPS ;
- limites upload ;
- en-têtes ;
- fichiers statiques ;
- timeouts.

---

# 45. HTTPS

Prévoir :

- certificat fourni par l’administrateur ;
- certificat d’une PKI interne ;
- certificat autosigné pour environnement de test.

Ne jamais dépendre obligatoirement d’une autorité de certification Internet.

---

# 46. AUTHENTIFICATION

Comptes locaux.

Rôles :

```text
administrateur
utilisateur
```

Mots de passe avec :

```text
Argon2id
```

ou solution équivalente actuelle reconnue.

---

# 47. SÉCURITÉ DOCUMENTAIRE

Se protéger contre :

- path traversal ;
- noms dangereux ;
- XSS ;
- MIME trompeur ;
- documents surdimensionnés ;
- ZIP bombs ;
- fichiers malformés ;
- injection HTML ;
- macros ;
- exécution de contenu utilisateur.

Ne jamais exécuter les macros d’un document.

---

# 48. MODE OFFLINE STRICT

Créer :

```text
OFFLINE_MODE=true
```

Lorsque actif :

- aucun téléchargement ;
- aucun appel API ;
- aucun CDN ;
- aucun modèle distant ;
- aucun fallback Internet ;
- erreur explicite si poids absent.

Configurer également lorsque pertinent :

```text
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_DATASETS_OFFLINE=1
```

et les mécanismes équivalents des autres bibliothèques.

---

# 49. BLOCAGE RÉSEAU OPTIONNEL

Créer un mode de durcissement permettant, si l’administrateur le souhaite, d’interdire réellement les connexions Internet sortantes du compte :

```text
docutranslate
```

Étudier :

- nftables par UID ;
- restrictions systemd ;
- mécanismes Ubuntu appropriés.

Le serveur web doit toujours rester accessible depuis le LAN.

Les communications locales vers PostgreSQL/Redis doivent continuer à fonctionner.

Documenter précisément les règles avant de les appliquer.

Ne jamais casser l’administration SSH du serveur.

---

# 50. STOCKAGE DES MODÈLES

Organisation suggérée :

```text
/opt/docutranslate/models/
├── docling/
├── paddleocr/
├── translation/
│   ├── opus-mt-en-fr/
│   ├── m2m100-418m/
│   └── madlad400-3b/
└── post-editing/
```

Chaque modèle doit avoir :

```text
manifest.json
checksum
licence
révision
source
```

---

# 51. GESTIONNAIRE DE MODÈLES

Créer une commande :

```bash
docutranslate-model
```

Fonctions souhaitées :

```text
list
info
verify
benchmark
enable
disable
set-default
```

Exemple :

```bash
docutranslate-model list
```

doit pouvoir afficher :

```text
MODEL               STATUS      PROFILE      LICENSE
opus-mt-en-fr       READY       light        Apache-2.0
m2m100-418m         READY       balanced     MIT
madlad400-3b        READY       quality      Apache-2.0
nllb-600m           DISABLED    test         CC-BY-NC-4.0
```

---

# 52. PAS DE TÉLÉCHARGEMENT DE MODÈLE DEPUIS L’INTERFACE EN MODE OFFLINE

En environnement isolé :

un administrateur doit installer les modèles au moyen d’un paquet transféré sur le serveur.

L’interface peut détecter et activer les modèles présents.

---

# 53. INSTALLATION CONNECTÉE

Créer :

```bash
sudo ./install.sh
```

Le script doit :

1. vérifier Ubuntu 24.04 ;
2. vérifier architecture CPU ;
3. installer les packages système ;
4. créer l’utilisateur ;
5. créer les répertoires ;
6. installer PostgreSQL ;
7. installer Redis si nécessaire ;
8. installer Nginx ;
9. créer les venv ;
10. installer les dépendances Python verrouillées ;
11. installer les fichiers applicatifs ;
12. configurer systemd ;
13. configurer Nginx ;
14. initialiser PostgreSQL ;
15. exécuter les migrations ;
16. créer l’administrateur ;
17. installer/vérifier les modèles sélectionnés ;
18. démarrer les services ;
19. lancer les healthchecks.

---

# 54. INSTALLATION TOTALEMENT AIR-GAPPED

C’est une fonction obligatoire.

Créer sur une machine Ubuntu 24.04 connectée :

```bash
./build-offline-bundle.sh
```

Le bundle devra contenir autant que légalement possible :

```text
application
wheelhouse Python
paquets .deb
modèles
assets
migrations
configurations
services systemd
configuration Nginx
manifest
checksums
documentation
```

---

# 55. WHEELHOUSE PYTHON

Préparer :

```text
offline/wheels/
```

contenant toutes les dépendances Python nécessaires.

Installation :

```bash
pip install \
  --no-index \
  --find-links=/media/bundle/wheels \
  ...
```

Le serveur isolé ne doit jamais contacter PyPI.

---

# 56. DÉPÔT APT LOCAL

Pour l’installation hors ligne, ne pas supposer que :

```bash
apt install ...
```

peut accéder à Internet.

Préparer :

```text
offline/apt/
```

contenant les `.deb` nécessaires.

Construire si pertinent un petit dépôt APT local :

```text
deb [trusted=yes] file:/... ./
```

ou une méthode plus propre signée localement.

Vérifier les dépendances récursives.

Tester l’installation sur un environnement réellement sans Internet.

---

# 57. BUNDLE OFFLINE

Exemple :

```text
docutranslate-offline-1.0.0-amd64.tar.zst
```

Il devra être accompagné de :

```text
SHA256SUMS
MANIFEST.json
LICENSES/
README-OFFLINE.txt
```

---

# 58. INSTALLATION OFFLINE

Créer :

```bash
sudo ./install-offline.sh
```

Aucun accès réseau externe ne doit être nécessaire.

---

# 59. GPU NVIDIA

Le GPU reste FACULTATIF.

Le logiciel doit fonctionner sans NVIDIA.

Si NVIDIA est présent :

- détecter le pilote ;
- vérifier CUDA compatible ;
- tester PyTorch ;
- tester VRAM ;
- sélectionner les optimisations appropriées.

Ne pas modifier aveuglément un pilote fonctionnel.

---

# 60. INSTALLATION GPU HORS LIGNE

Prévoir également la possibilité d’utiliser une machine isolée équipée NVIDIA.

Attention aux licences de redistribution.

Si les pilotes/CUDA ne peuvent légalement être inclus dans le bundle principal :

- documenter leur téléchargement préalable ;
- fournir les checksums ;
- permettre l’installation depuis un dépôt local ;
- détecter un pilote déjà présent.

---

# 61. DIAGNOSTIC

Créer :

```bash
sudo /opt/docutranslate/bin/diagnose
```

Afficher :

```text
OS
kernel
CPU
cores
RAM
swap
disque
GPU
VRAM
driver
CUDA
Python
PostgreSQL
Redis
Nginx
modèles installés
modèle actif
worker
mode offline
```

---

# 62. ADMINISTRATION WEB — MATÉRIEL

Créer une page :

**Système**

Afficher :

```text
CPU
RAM
GPU
VRAM
stockage
workers
queue
```

---

# 63. ADMINISTRATION WEB — MODÈLES

Page :

**Modèles IA**

Afficher chaque modèle avec :

```text
nom
version
licence
taille
CPU/GPU
état
RAM
VRAM
score benchmark
vitesse
profil
actif/inactif
```

Permettre :

```text
Tester
Benchmarker
Activer
Désactiver
Définir par défaut
```

---

# 64. RECOMMANDATION AUTOMATIQUE

Après benchmark, afficher par exemple :

```text
Configuration détectée :

AMD Ryzen ...
32 Go RAM
NVIDIA RTX ...
12 Go VRAM

Recommandations :

Rapide :
OPUS-MT EN→FR

Équilibré :
M2M100 418M

Qualité :
MADLAD-400 3B
```

Ces choix doivent résulter des mesures réelles.

---

# 65. CONFIGURATIONS CIBLES

## MINIMUM

```text
CPU x86-64 récent
16 Go RAM
SSD
sans GPU
```

L’application doit fonctionner.

---

## RECOMMANDÉ

```text
CPU 8 cœurs environ
32 Go RAM
SSD/NVMe
GPU NVIDIA 12-16 Go
```

---

## HAUT DE GAMME

```text
64 Go RAM
GPU 16-24 Go VRAM
NVMe
```

Ne jamais rendre cette configuration obligatoire.

---

# 66. QUANTIFICATION

Tester lorsque pertinent :

- FP32 ;
- FP16 ;
- BF16 ;
- INT8 ;
- autres formats stables.

Mais :

ne pas supposer qu’une quantification donne automatiquement de meilleurs résultats.

Mesurer :

```text
qualité
RAM
VRAM
vitesse
stabilité
```

---

# 67. CPU

Optimiser raisonnablement :

- threads ;
- batch ;
- BLAS ;
- nombre de workers.

Ne jamais saturer complètement la machine au point de rendre l’interface inutilisable.

---

# 68. BASE DE DONNÉES DES BENCHMARKS

Conserver :

```text
modèle
version
révision
matériel
date
configuration
RAM
VRAM
temps
scores
```

Cela permettra de comparer les modèles ultérieurement.

---

# 69. CHANGEMENT DE MODÈLE

Un administrateur doit pouvoir changer le moteur sans réinstaller l’application.

Procédure :

```text
validation nouveau modèle
→ chargement
→ healthcheck
→ bascule
```

En cas d’échec :

```text
retour à l’ancien modèle
```

---

# 70. TÂCHES EXISTANTES

Lorsqu’un modèle par défaut change, ne pas changer arbitrairement le moteur d’un job déjà démarré.

Stocker avec chaque job :

```text
model_id
model_version
```

---

# 71. SAUVEGARDE

Créer :

```bash
backup.sh
restore.sh
```

Sauvegarder :

- PostgreSQL ;
- configuration ;
- comptes ;
- glossaire ;
- mémoire ;
- paramètres ;
- métadonnées modèles.

Permettre d’inclure ou d’exclure :

- uploads ;
- outputs ;
- modèles.

---

# 72. LOGS

Utiliser journald et/ou fichiers dédiés.

Ne jamais journaliser inutilement le texte confidentiel.

Logs :

```text
job
état
durée
moteur
version
erreur
RAM/VRAM
```

---

# 73. LOGROTATE

Créer une configuration :

```text
/etc/logrotate.d/docutranslate
```

si des journaux fichiers sont utilisés.

---

# 74. HARDENING SYSTEMD

Appliquer raisonnablement :

```text
NoNewPrivileges
PrivateTmp
ProtectSystem
ProtectHome
ReadWritePaths
UMask
```

et autres protections compatibles.

Tester après chaque durcissement.

Ne pas copier aveuglément des directives qui cassent PyTorch/CUDA.

---

# 75. SERVICES

Créer des fichiers propres :

```text
/etc/systemd/system/docutranslate-web.service
/etc/systemd/system/docutranslate-worker.service
/etc/systemd/system/docutranslate-translation.service
```

Avec :

```text
User=docutranslate
Group=docutranslate
Restart=on-failure
```

et dépendances appropriées.

---

# 76. HEALTHCHECKS

Créer :

```text
/health
```

pour l’application.

Créer aussi une commande :

```bash
docutranslate-health
```

Vérifier :

```text
web
database
redis
worker
OCR
translation runtime
model
storage
```

---

# 77. ERREURS

Aucune page blanche.

Exemple :

```text
MADLAD-400 3B indisponible :
VRAM insuffisante.

Utilisation de OPUS-MT.
```

ou :

```text
Aucun modèle de traduction utilisable.

Installez un modèle dans :
/opt/docutranslate/models/translation/
```

---

# 78. TESTS UNITAIRES

Couvrir :

```text
segmentation
glossaire
placeholders
nombres
unités
références
mémoire
choix moteur
model registry
licences
offline
uploads
permissions
```

---

# 79. DOCUMENTS DE TEST

Générer des documents fictifs.

## A

PDF natif avec :

- titres ;
- tableaux ;
- images ;
- valeurs ;
- références.

## B

PDF scanné.

## C

DOCX.

## D

PPTX.

## E

Image annotée.

---

# 80. DOCUMENT TECHNIQUE DE VALIDATION

Inclure :

```text
Power supply voltage: 12 VDC.
Connect J3 to the STM32F407 control board.
Maximum torque is 4.5 Nm.
Use the M4x20 screws.
Communication uses CAN and RS-485.
```

Le résultat français doit conserver exactement :

```text
12 VDC
J3
STM32F407
4.5 Nm
M4x20
CAN
RS-485
```

---

# 81. COMPARAISON DES MODÈLES

Tester LE MÊME document avec tous les moteurs installés.

Produire un tableau :

```text
                 OPUS     M2M100     MADLAD
------------------------------------------------
Temps
RAM
VRAM
Nombres OK
Références OK
Glossaire OK
Score qualité
```

Ne pas choisir arbitrairement le plus gros modèle.

---

# 82. TEST AIR-GAPPED OBLIGATOIRE

Tester réellement :

```text
Internet indisponible
```

Puis :

```text
redémarrage serveur
→ lancement services
→ connexion web LAN
→ upload PDF
→ OCR
→ traduction
→ reconstruction
→ téléchargement
```

Le test doit réussir.

---

# 83. TEST DES APPELS SORTANTS

Pendant le test offline, surveiller les connexions réseau de l’application.

Identifier toute tentative vers :

```text
Hugging Face
GitHub
Google
PyPI
Paddle
CDN
analytics
autre
```

Les supprimer.

---

# 84. DÉPÔT GIT

Organisation suggérée :

```text
docutranslate/
├── app/
│   ├── web/
│   ├── auth/
│   ├── documents/
│   ├── models/
│   ├── translation/
│   ├── ocr/
│   ├── glossary/
│   ├── memory/
│   ├── jobs/
│   ├── quality/
│   ├── reconstruction/
│   ├── templates/
│   └── static/
│
├── services/
│   ├── translation_runtime/
│   └── worker/
│
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│
├── packaging/
│   ├── systemd/
│   ├── nginx/
│   ├── apt/
│   └── offline/
│
├── scripts/
├── docs/
├── requirements/
├── pyproject.toml
├── .env.example
├── Makefile
└── README.md
```

Adapter si une meilleure structure apparaît.

---

# 85. VERROUILLAGE DES VERSIONS

Le déploiement doit être reproductible.

Épingler les versions testées.

Utiliser :

```text
requirements.lock
uv.lock
pip-tools
```

ou mécanisme équivalent fiable.

Documenter :

```text
Python
PyTorch
Transformers
Docling
PaddleOCR
FastAPI
PostgreSQL
Redis
Nginx
CUDA
```

---

# 86. FICHIERS DE CONFIGURATION

Créer :

```text
/etc/docutranslate/docutranslate.env
```

avec permissions restrictives.

Fournir :

```text
.env.example
```

sans secrets.

---

# 87. PARAMÈTRES

Prévoir :

```text
OFFLINE_MODE=true

TRANSLATION_PROFILE=auto
TRANSLATION_MODEL=

MODEL_ROOT=
OCR_MODEL_ROOT=
DOCLING_MODEL_ROOT=

WORKER_COUNT=
GPU_CONCURRENCY=

UPLOAD_MAX_SIZE=
DOCUMENT_RETENTION_DAYS=

LOG_LEVEL=
```

---

# 88. DOCUMENTATION

Créer :

```text
README.md
ARCHITECTURE.md
INSTALL_UBUNTU_24_04.md
OFFLINE_INSTALL.md
GPU_INSTALL.md
MODELS.md
MODEL_BENCHMARKS.md
USER_GUIDE.md
ADMIN_GUIDE.md
SECURITY.md
BACKUP_RESTORE.md
UPDATE.md
ROLLBACK.md
TROUBLESHOOTING.md
LICENSES.md
```

---

# 89. LICENCES

Pour CHAQUE modèle et composant :

vérifier la licence actuelle.

Ne jamais déduire la licence à partir d’une information ancienne.

Créer :

```text
LICENSES.md
```

avec :

```text
nom
version
URL/source
licence
restrictions
redistribution
usage commercial
```

---

# 90. INSTALLATION DES MODÈLES

Prévoir un mécanisme connecté uniquement pour la préparation :

```bash
prepare-model.sh MODEL_ID
```

Il doit :

```text
télécharger
figer révision
vérifier fichiers
calculer SHA256
créer manifest
```

Ensuite le modèle doit être transférable hors ligne.

---

# 91. PAS DE TÉLÉCHARGEMENT INVISIBLE

Tout téléchargement effectué pendant la préparation doit être explicite.

Après passage en production offline :

**zéro téléchargement.**

---

# 92. MISE À JOUR APPLICATION

Créer une procédure native :

```text
backup
→ arrêt services
→ déploiement nouvelle version
→ création/mise à jour venv
→ migration DB
→ systemctl daemon-reload
→ démarrage
→ healthcheck
```

---

# 93. ROLLBACK

Conserver au minimum les deux versions applicatives :

```text
/opt/docutranslate/releases/1.0.0
/opt/docutranslate/releases/1.1.0
```

avec :

```text
/opt/docutranslate/current
```

comme lien symbolique.

Cela doit permettre un rollback rapide lorsque les migrations le permettent.

---

# 94. INSTALLATION ATOMIQUE

Privilégier :

```text
releases/version
→ tests
→ current -> version
→ restart
```

plutôt qu’une modification désordonnée des fichiers en production.

---

# 95. COMPTE ADMINISTRATEUR

Ne jamais fournir un mot de passe par défaut codé en dur.

À l’installation :

- générer un mot de passe temporaire fort

OU

- demander sa création.

---

# 96. PAGE D’ACCUEIL ADMINISTRATEUR

Afficher :

```text
Application             OK
Mode hors ligne          ACTIF
PostgreSQL               OK
Redis                    OK
Worker                   OK
OCR                      OK
Translation runtime      OK

Moteur actuel :
MADLAD-400 3B

GPU :
NVIDIA ...

VRAM :
... / ...

Jobs :
...
```

---

# 97. PRIORITÉ DES PHASES

## PHASE 1 — SOCLE NATIF

- dépôt ;
- FastAPI ;
- PostgreSQL ;
- Nginx ;
- systemd ;
- authentification.

## PHASE 2 — MOTEUR LÉGER

- TranslationEngine ;
- Model Registry ;
- OPUS-MT ;
- tests.

## PHASE 3 — MOTEURS ALTERNATIFS

- M2M100 ;
- MADLAD ;
- benchmarks ;
- choix automatique.

## PHASE 4 — DOCUMENTS

- Docling ;
- PDF ;
- DOCX ;
- tableaux.

## PHASE 5 — OCR

- PaddleOCR ;
- PDF scannés.

## PHASE 6 — RECONSTRUCTION

- PDF ;
- DOCX ;
- images.

## PHASE 7 — TEXTE DANS LES IMAGES

- OCR ;
- traduction ;
- remplacement graphique.

## PHASE 8 — QUALITÉ

- glossaire ;
- mémoire ;
- vérifications ;
- comparaison modèles.

## PHASE 9 — OFFLINE

- wheelhouse ;
- packages DEB ;
- modèles ;
- bundle.

## PHASE 10 — INDUSTRIALISATION

- sécurité ;
- backup ;
- rollback ;
- monitoring local ;
- documentation.

---

# 98. COMPORTEMENT ATTENDU DE CHATGPT WORK

**NE VOUS LIMITEZ PAS À PRODUIRE UNE ARCHITECTURE OU DU CODE THÉORIQUE.**

Votre travail consiste à avancer réellement dans la réalisation.

Vous devez :

1. examiner l’environnement ;
2. créer le dépôt/projet ;
3. écrire les fichiers ;
4. exécuter le code ;
5. installer les dépendances nécessaires dans l’environnement de travail ;
6. lancer les tests ;
7. lire les erreurs ;
8. corriger ;
9. relancer ;
10. mesurer ;
11. documenter ;
12. continuer tant que les outils disponibles permettent de progresser.

Une modification n’est pas considérée comme correcte parce qu’elle « semble correcte ».

**ELLE DOIT ÊTRE TESTÉE.**

---

# 99. AUTONOMIE DE CHATGPT WORK

Ne me demander un choix que lorsqu’il est réellement nécessaire.

Pour les décisions techniques courantes :

```text
analyser
→ choisir
→ tester
→ documenter
→ continuer
```

Ne pas interrompre le travail pour demander :

```text
OPUS ou M2M100 ?
```

Tester les deux si possible.

Puis présenter les résultats.

---

# 100. NE PAS FIGER PRÉMATURÉMENT LE MODÈLE IA

C’est une exigence importante.

L’objectif n’est PAS :

```text
utiliser MADLAD coûte que coûte
```

L’objectif est :

```text
trouver le meilleur compromis
qualité / vitesse / matériel / licence
```

sur la machine cible.

Les modèles proposés dans ce prompt sont des candidats, pas des obligations définitives.

---

# 101. CRITÈRES DE CHOIX DU MODÈLE PAR DÉFAUT

Dans cet ordre :

1. licence compatible avec l’usage prévu ;
2. fonctionnement totalement local ;
3. conservation des données techniques ;
4. qualité anglais → français ;
5. stabilité ;
6. consommation mémoire ;
7. vitesse ;
8. simplicité d’installation.

---

# 102. CRITÈRES DE VALIDATION V1

La V1 ne sera considérée fonctionnelle que si les tests suivants ont réellement réussi.

## TEST 1

```text
PDF texte
→ upload
→ traduction
→ PDF/DOCX français
```

## TEST 2

```text
PDF scanné
→ OCR
→ traduction
→ export
```

## TEST 3

```text
DOCX
→ traduction texte
→ tableaux
→ images conservées
→ DOCX
```

## TEST 4

Les références techniques ne changent pas.

## TEST 5

Le glossaire est appliqué.

## TEST 6

Au moins deux modèles de traduction peuvent être sélectionnés si le matériel le permet.

## TEST 7

Le changement de modèle ne nécessite pas de réinstallation complète.

## TEST 8

Le mode automatique choisit seulement un modèle présent localement.

## TEST 9

L’application fonctionne CPU uniquement.

## TEST 10

Lorsque GPU disponible, l’accélération fonctionne réellement.

## TEST 11 — CRITIQUE

```text
AUCUN ACCÈS INTERNET
```

Puis :

```text
redémarrage
→ connexion LAN
→ upload
→ OCR
→ traduction
→ reconstruction
→ téléchargement
```

Le résultat doit fonctionner normalement.

---

# 103. LIVRABLE FINAL

Fournir un rapport factuel indiquant :

```text
fonctionnalités implémentées
tests réellement exécutés
tests réussis
tests échoués
modèles installés
modèle recommandé
modèle rapide
modèle qualité
scores
RAM
VRAM
temps de traitement
formats supportés
limitations
procédure installation
procédure offline
backup
restore
update
rollback
diagnostic
```

Ne jamais présenter une fonctionnalité comme terminée si elle n’a pas été testée.

---

# 104. OBJECTIF FINAL

Je veux obtenir un système ressemblant à ceci :

```text
               DOCUTRANSLATE LOCAL
                      │
            ┌─────────┴──────────┐
            │                    │
          WEB LAN             ADMIN
            │                    │
            ▼                    ▼
        DOCUMENT             MODÈLES IA
            │                    │
            ▼                    │
         DOCLING                 │
            │                    │
       ┌────┴────┐               │
       │         │               │
      OCR      TEXTE             │
       │         │               │
       └────┬────┘               │
            ▼                    │
       PROTECTION                │
            │                    │
         GLOSSAIRE               │
            │                    │
            ▼                    │
       MODEL REGISTRY ◄──────────┘
            │
     ┌──────┼──────────┐
     ▼      ▼          ▼
   OPUS   M2M100     MADLAD
     │      │          │
     └──────┴────┬─────┘
                 ▼
          CONTRÔLE QUALITÉ
                 │
                 ▼
          RECONSTRUCTION
                 │
          ┌──────┴──────┐
          ▼             ▼
        DOCX           PDF
```

Le serveur final doit être :

- autonome ;
- local ;
- confidentiel ;
- sans Docker ;
- administrable ;
- évolutif ;
- capable d’utiliser plusieurs moteurs IA ;
- capable de fonctionner sur CPU ;
- capable de tirer parti d’un GPU gaming ;
- entièrement fonctionnel sans Internet.

Commencez maintenant par examiner l’environnement à votre disposition, les versions actuelles des composants et les licences des modèles candidats.

Ensuite construisez effectivement le projet.

Ne vous arrêtez pas après l’étude d’architecture.