# Validation de la refonte contexte / mise en page — 14 octobre 2026

Les modifications de l’application restent sur `refonte-contexte-mise-en-page` (PR #4). Elles ne sont pas fusionnées dans main.

## Référence de production

Le code de traduction de l’itération 11, version de contrôle `ffeeff6f1872e4166078ba2e8816312e6dcf90aa`, a été retraduit le 14 octobre : 123 segments L3Harris terminés en 179 secondes, 43 avertissements de mise en page et aucune nouvelle alerte technique. Exécution GitHub Actions : https://github.com/pigeonfou/DocTrad/actions/runs/38494535387

## Expériences sur la branche

Les variantes ont été déployées et testées réellement. Des contrôles ont interrompu les traductions pour référence absente, réponse contenant une autre écriture ou connexion distante interrompue. Le dernier candidat `41dfb04753febf8314ae8d3aa46f5ef927b72b4a` passe 273 tests, mais son essai réel termine en échec à 40 % (55 segments enregistrés, aucune alerte technique sur les segments enregistrés, puis missing_identifier dans la cellule Windows/CPA/WebUI). Aucun PDF final validé de la refonte n’a été produit.

L’enrichissement de contexte a été réduit aux petites cellules ; le prompt de prose validé a été rétabli. Les listes d’identifiants dans les relances ont été supprimées. Le contrôle d’acronymes est dérivé de la source, la reprise réseau reste bornée à une relance et la reconstruction exploite davantage d’espace vérifié libre. Ces changements demeurent expérimentaux tant qu’une traduction complète ne passe pas.

Le test de placement seul, en réutilisant exactement les traductions de l’itération 11, réduit les avertissements de 43 à 42 sans nouveau type d’avertissement. Ce résultat ne prouve pas la qualité d’une nouvelle traduction.

## Décision

Revenir au code de production déjà validé pour respecter l’objectif de progression sans régression. Ce commit documentaire ne change aucun module applicatif ; son déploiement remet la référence de production sur le serveur avec les contrôles habituels. Conserver la branche pour revoir la récupération des références avant un nouvel essai réel.
