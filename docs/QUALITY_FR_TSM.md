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
