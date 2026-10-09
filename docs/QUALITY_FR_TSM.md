# Qualité EN → FR : référence TSM WAVEFORM

Le chemin utilisé par le worker transmet maintenant le texte source complet au
moteur local. Les nombres, unités et appellations commerciales ne fragmentent
plus l'inférence en petits morceaux. L'ancien protocole à marqueurs reste
compatible avec les clients existants.

Les lignes OCR alignées dans un même paragraphe sont regroupées, avec maintien
des boîtes individuelles. Les titres, listes, colonnes et cellules restent
séparés. Le PDF replie les traductions des paragraphes dans leur zone d'origine
et masque uniquement les anciennes lignes, en conservant le fond graphique.

Les titres exacts utilisent le glossaire local, dont les entrées utilisateur ont
priorité. Les contrôles signalent les nombres, références et appellations
modifiés, les confusions terminologiques connues et certaines unités critiques
perdues. Ces contrôles s'appliquent aussi aux corrections manuelles avant leur
ajout à la mémoire de traduction. Ils ne réécrivent pas une valeur douteuse.

La référence ChatGPT constitue un exemple de lisibilité, pas une traduction
à recopier sans vérification. Toute reformulation doit être confrontée au
texte anglais ; aucune information technique nouvelle ne doit être ajoutée.

Les tests de contexte emploient une inférence simulée ; ils vérifient les
entrées réelles du modèle et le protocole, pas la qualité linguistique d'un
modèle entraîné. La fixture PDF raster TSM vérifie les coordonnées, les tableaux
et la conservation de l'illustration. Le test de paragraphe vérifie une vraie
recomposition PDF avec extraction du texte final. La qualité linguistique doit
encore être évaluée avec le modèle installé et le document complet.

Les tableaux bordés disposent désormais de cellules physiques (traits verticaux
et horizontaux). Leur lecture groupe les continuations avant de passer à la
colonne voisine, sans fusionner deux lignes du tableau ni deux puces.
Les symboles de puce n'abaissent plus la confiance des mots de leur ligne.
Les marques seules, y compris leurs lettres espacées par l'OCR, conservent
leur graphisme original ; les listes constituées exclusivement de produits,
références et acronymes ne passent pas par l'inférence.

Une valeur omise après un acronyme entre parenthèses peut être restaurée à
ce repère si celui-ci n'apparaît qu'une fois dans la source et la traduction.
Une valeur déjà présente mais différente reste signalée, sans correction
automatique ambiguë. Les contrôles acceptent la virgule décimale française
et les espaces autour des unités.

OPUS Big EN→FR est disponible comme option équilibrée, avec poids Safetensors
vérifiés. Son ajout ne change pas le modèle par défaut : le choix administratif
explicite nécessite authentification, droits administrateur, CSRF et modèle
installé, vérifié, activé et compatible avec les ressources disponibles.
Le nombre de paramètres n'est pas considéré comme une preuve de qualité.

Les titres connus du glossaire ne sont plus interprétés comme des références
techniques modifiées du seul fait de leur traduction. Les acronymes au pluriel
(SDRs → SDR) gardent leur nombre d'occurrences. Les données chiffrées et les
appellations commerciales restent contrôlées séparément. Les réparations de
formulations françaises observées sont limitées aux expressions techniques
présentes dans leur source anglaise ; elles ne remplacent pas un paragraphe
entier par une traduction de référence. Le slogan graphique de la marque est
conservé pour éviter de redessiner des ornements confondus avec des caractères.

Les doubles mesures (par exemple miles et kilomètres) restent intégrales.
Lorsqu'un moteur conserve seulement la conversion, la mesure principale est
restaurée depuis la source uniquement si la valeur et l'unité conservées
identifient un rapprochement unique. Les valeurs changées, unités changées et
ancres répétées restent signalées pour vérification.
