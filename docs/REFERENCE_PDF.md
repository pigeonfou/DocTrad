# Document de référence : TSM Waveform

Document fourni par l'utilisateur : fiche TrellisWare Technologies, septembre 2022.
Le PDF original, avec ses mentions de droits, est conservé sans modification dans
`tests/fixtures/tsm-waveform-reference.pdf`. Utilisation pour validation du projet,
sans présumer qu'un document publiquement accessible possède une licence libre.

SHA-256 : `9bc58a21ffa56f89dcec9e201f17d77b606135462a9c23b8e23fc274467b9e4b`.
Deux pages Letter, 612 × 792 points ; chaque page est une image de 1700 × 2200
pixels à 200 dpi. Aucun texte natif extractible. Présence de photos, logos, QR code,
paragraphes, listes, tableau technique et petits caractères.

## Export PDF visuel

Poppler rend les pages localement, Tesseract fournit les coordonnées et la confiance.
Le même rendu à 2500 pixels sert à l'analyse et à l'export, avec CropBox et rotation.
Chaque page entière sert de fond ; les traductions sont superposées dans les seules
zones de texte reconnues, avec une couleur de fond et de texte estimée localement.
Les grandes séparations horizontales OCR délimitent les cellules de tableau.
Les coordonnées enregistrées des segments sont réutilisées après correction humaine.

Le nombre et les dimensions des pages sont conservés. Les illustrations restent dans
le fond. Le PDF exporté est un document visuel raster avec du texte traduit superposé,
pas une restitution éditable des vecteurs ou des polices originales. Le DOCX associé
reste une version de texte destinée à la révision ; sa mise en page n'est pas fidèle.

Les zones OCR très incertaines, sur fond complexe ou dont la traduction ne tient pas
avec une police d'au moins 5 points sont conservées en anglais et signalées dans les
avertissements du segment et dans `layout-report.json`. Les polices réduites sont
également signalées. Cette conservation évite un résultat illisible ou la destruction
d'une illustration ; elle ne constitue pas une traduction complète validée.

## Vérification

`tests/test_pdf_layout.py` vérifie le nombre et les dimensions des pages, le texte
français superposé, la conservation d'une figure colorée, le refus des coordonnées
invalides et le signalement des débordements. Le vrai document vérifie l'intégrité
du fichier, l'OCR, la séparation des en-têtes de tableau et l'export des deux pages.
Les substitutions françaises de ce test sont fixées : il teste l'export, pas la qualité
linguistique du modèle. Une relecture visuelle et technique reste nécessaire pour
une traduction réelle, notamment les unités, fréquences, références et petites notes.
