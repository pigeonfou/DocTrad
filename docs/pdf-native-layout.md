# PDF natifs et PDF scannés

DocTrad utilise d'abord `pdftotext -bbox-layout` (Poppler, déjà installé) pour
obtenir les mots et leurs coordonnées sur chaque page contenant du texte natif.
Les rectangles adjacents du PDF identifient les cellules et les en-têtes des
tableaux. Les blocs et leurs colonnes restent séparés ; les lignes d'un même
paragraphe sont regroupées avant traduction. Les tailles et graisses sont
récupérées depuis les opérateurs texte PDF lorsque leur correspondance est sûre.

Les pages sans texte natif restent traitées par Tesseract. Une page contenant
une image et seulement quelques mots natifs utilise également l'OCR, afin de
ne pas ignorer un scan sous une légende. Les PDF hybrides complexes demandent
encore une vérification humaine : le chemin natif ne complète pas automatiquement
chaque illustration par une seconde lecture OCR.

Les chevrons devant du texte sont des marqueurs de liste ; un opérateur devant
une valeur numérique reste une comparaison. Les exposants des volumes en pouces
sont conservés et les réparations numériques s'appuient sur des unités uniques.
Les illustrations et les inscriptions tournées identifiées sont préservées.
Le masquage natif protège les traits horizontaux longs, notamment les soulignements.

L'export garde les images comme fond de page : il ne reconstruit pas les objets
vectoriels du document original. Les photographies derrière un texte et les fonds
complexes peuvent rester en anglais avec un avertissement dans le rapport de mise
en page. Le PDF traduit doit toujours être relu avant diffusion.
