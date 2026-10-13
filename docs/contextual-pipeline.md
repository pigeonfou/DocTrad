# Traduction avec contexte et placement contraint

Branche expérimentale : `refonte-contexte-mise-en-page`.

## Parcours

1. Extraire le texte et conserver les pages, colonnes, cellules, puces et coordonnées.
2. Construire un contexte source borné pour chaque passage : section, cellule voisine de la même ligne ou passages adjacents de la même colonne.
3. Envoyer le passage original et son contexte au moteur distant. Le contexte sert au sens et ne fait pas partie du texte à traduire.
4. Contrôler les nombres, unités et références après génération. Les listes d'identifiants à recopier et les noms propres fixes ont été retirés des prompts. Le glossaire reste limité aux termes présents dans le passage.
5. Placer la traduction dans la zone originale, puis exploiter jusqu'à trois lignes d'espace supplémentaire vérifié libre avant de réduire la police. Les pixels contrastés, blocs voisins, cellules et illustrations arrêtent l'extension.
6. Produire le rapport de qualité et conserver les corrections humaines.

Le contexte reste sur le réseau privé de traduction. Il n'est jamais inscrit dans les journaux d'erreur. Le moteur local garde son interface et son comportement existants. Les mémoires validées de l'utilisateur restent prioritaires.

## Validation avant intégration

- Tests des frontières de page, colonne et cellule ; absence de contexte résiduel entre requêtes.
- Tests de conservation technique après suppression des listes dans les prompts.
- Tests PDF de lisibilité et d'absence de collision avec tableaux, puces, images et pieds de page, notamment la référence TrellisWare.
- Traduction réelle comparative de la référence L3Harris sur un environnement de validation avant fusion. Une baisse globale des avertissements ne suffit pas si une valeur ou une zone régresse.

Cette branche ne remplace pas encore le fond raster par une reconstruction vectorielle complète. Une telle étape nécessite une représentation commune des blocs et un corpus de pages plus varié ; elle ne doit pas supprimer les garde-fous de placement existants.
