# Branche OpenDataLoader

Base : refonte-contexte-mise-en-page, bd7177f. Analyseur : opendataloader-pdf 2.5.13, Apache-2.0, Java 11 minimum (JRE système).

## Chaîne intégrée

PDF -> OpenDataLoader local -> JSON structuré -> segments DocTrad -> glossaire / TranslateGemma -> contrôles -> export PDF existant.

OpenDataLoader remplace, pour les pages prises en charge, l'extraction native, l'ordre de lecture, le regroupement des paragraphes, la détection des titres et des cellules. Les identifiants de structure et le contexte section/ligne sont conservés et consommés par document_context. Les coordonnées PDF sont converties au repère Poppler 2500 pixels, avec CropBox et rotation.

Le paquet et son JAR sont installés à l'avance : aucun téléchargement pendant l'analyse. L'installation et le bundle hors ligne incluent le JRE. Le JSON temporaire est supprimé à la fin. L'anonymisation n'est pas activée : les valeurs techniques et contacts doivent rester fidèles. Aucune description générative d'image n'est utilisée comme texte source.

## Modes

- `DOCTRAD_PDF_BACKEND=opendataloader` : valeur par défaut sur cette branche.
- `DOCTRAD_PDF_BACKEND=legacy` : chaîne historique pour comparaison / retour arrière.
- `DOCTRAD_ODL_HYBRID_URL=http://127.0.0.1:5002` : utilise l'API hybride docling-fast, mode full, uniquement sur loopback. Ce service optionnel doit être installé dans son propre environnement, avec ses modèles déjà provisionnés et ses téléchargements désactivés. Cette branche ne l'installe ni ne l'active automatiquement. Il n'a pas été validé ici.

Le mode local ne fait pas d'OCR des pages image. Ces pages sont récupérées par Tesseract local. Les tables regroupées à tort en deux grandes lignes contenant plus de cinq lignes de texte sont récupérées par l'analyse géométrique historique. Une panne du paquet/Java ne déclenche pas un basculement silencieux : le travail échoue explicitement.

## Limites observées

Sur L3Harris : 118 segments, dont 23 OpenDataLoader et 95 issus de la récupération des tableaux. Les occurrences numériques sont conservées par rapport aux 123 segments historiques. Les en-têtes/pieds de page peuvent être regroupés différemment. Le mode cluster ne corrige pas les tableaux fusionnés de ce document.

La référence TrellisWare est analysée avec la récupération OCR locale. Un PDF natif synthétique valide séparément l'exécution réelle du JAR.

OpenDataLoader n'est pas un traducteur et ne réinsère pas le français dans le PDF. TranslateGemma, le glossaire, les contrôles, la mémoire de traduction et l'export restent en place. La mise en page n'est donc pas réputée améliorée par cette seule intégration.

## Validation et déploiement

Les tests historiques tournent en mode legacy pour mesurer la compatibilité ; les tests dédiés appellent réellement OpenDataLoader indépendamment de ce réglage. Ils vérifient les repères, le contexte, la récupération des tables fusionnées, un PDF natif et la référence publique scannée.

OpenDataLoader n'est pas dans la liste des branches autorisées au déploiement du serveur : aucune modification de production, aucune fusion dans main. Le déploiement nécessitera la disponibilité du JRE dans OneForAll, puis une traduction complète et une revue du PDF.
