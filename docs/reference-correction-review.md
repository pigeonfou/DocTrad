# Corrections avant la prochaine traduction de référence

Le dernier résultat récupéré directement sur doctrad est le travail
`810b1355-4da3-44f2-8425-761ed160966d` : 120 segments, 146 secondes et
103 avertissements cumulant contrôles techniques et mise en page. Sa source
est le PDF public L3Harris AN/PRC-167 identifié par SHA-256
`cc6a5ca2bd9fad41fce19136afd7aaca3315a783a52348a4984bf11d8b8e41f6`.
Le PDF récupéré est identique, octet pour octet, à la précédente pièce jointe
`traduction-12.pdf` : il n'existe donc pas encore de résultat plus récent à évaluer.

| Défaut observé | Correction et portée |
|---|---|
| `TOP SECRET` remplacé par `CONFIDENTIEL` ; SAASM/ISR/COP/WebUI omis | Protection des désignations et seconde traduction avec les données conservées hors du modèle, déjà installées ; à mesurer sur une nouvelle traduction. |
| `30-2600 MHz` et `5 kHz-40 MHz` devenus des intervalles négatifs | Réparation des anciennes valeurs ; ajout du cas d'intervalles à unités différentes. Les valeurs réellement négatives restent négatives. |
| Unités `in` et `cm` absentes des dimensions | Restauration uniquement lorsque les trois valeurs correspondent à un unique groupe source/cible, déjà installée et visible au réexport. |
| SINAD devenu « rapport signal/bruit », VDC devenu VCC ; Suite A/B devenues « modèles A/B » | Désignations supplémentaires protégées, sans modifier les valeurs numériques ni supprimer les corrections utilisateur. |
| « radio multifréquences » et « bande croisée » | Réparations contextualisées en « radio multicanal » et « interconnexion interbande ». |
| Rubriques Voice/Data fusionnées et répétition de Voice dans Data | Séparation des sous-rubriques natives avant inférence ; leurs lignes restent dans la même cellule. |
| En-têtes anglais conservés ou polices réduites par des libellés trop longs | Glossaire concis des en-têtes et libellés, notamment « Pas / largeur de bande ». |
| Fragmentation de « U.S. Department… » | Découpage des phrases respectant les abréviations pointées. |
| Adresses, versions et mesures inchangées signalées comme non traduites | Reconnaissance des métadonnées et références littérales ; réduction de ces faux avertissements. |

La vérification visuelle effectuée ici est un réexport de contrôle des textes
déjà produits, avec le moteur PDF actuel. Elle ne constitue pas une nouvelle
inférence Unsloth. Elle confirme le nettoyage des cellules et la restauration
des dimensions. L'ancien texte reste trop long dans la petite mention sur la
photo et une valeur de puissance : aucune zone n'est forcée au-delà de sa place.
Le prompt demande désormais une rédaction technique concise, sans expansion
des sigles ni point final ajouté aux libellés.
Les avertissements de mise en page passent de 64 à 59 dans ce réexport contrôlé.
Ce compteur ne doit pas être comparé directement aux 103 avertissements globaux,
qui incluent les contrôles de terminologie et de données techniques.

La prochaine itération devra mesurer la conservation des désignations, la
séparation Voice/Data, la lisibilité des petits champs et les deux zones encore
conservées. Elle ne doit être lancée qu'après présentation de ces conclusions.
