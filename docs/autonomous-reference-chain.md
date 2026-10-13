# Chaîne autonome DocTrad

## Opérations disponibles

| Opération | Effet |
|---|---|
| `probe` | Vérifie la présence de la référence, le runtime et les capacités du lanceur ; ne charge aucun modèle et ne lance aucune traduction. |
| `latest` | Récupère le dernier résultat terminé issu d'un document public de référence reconnu. |
| `run` | Crée un travail dans la vraie file du worker, sous un compte de test isolé sans mémoire de traduction, puis suit son exécution. |
| `status` | Récupère l'état, les segments disponibles et les diagnostics du dernier test autonome, même après un échec. |

Les références autorisées sont les PDF publics L3Harris AN/PRC-167 et TrellisWare
TSM déjà utilisés dans ce projet. Leurs SHA-256 figurent dans `app/automation.py`
et dans le lanceur. Les fichiers dont le contenu ne correspond pas à ces SHA
ne sont pas exportés. Les comptes, mots de passe, clés et configurations ne font
pas partie des artefacts. L'authentification web et l'accès réseau public restent
inchangés.

`run` utilise le modèle sélectionné dans l'application. La configuration actuelle
de chargement automatique Unsloth et de contexte est donc appliquée par le worker.
Une seule traduction de référence reste active ; une nouvelle demande retrouve
le travail actif au lieu de le dupliquer. Aucun résultat en mémoire utilisateur
n'est effacé. Les tests, les déploiements et les récupérations Actions partagent
une même file d'opérations serveur pour éviter un redémarrage pendant un essai.

## Activation unique

Le déploiement automatique installe les nouveaux fichiers applicatifs. Le
lanceur déjà installé ne peut pas élargir lui-même ses commandes lors de cette
première activation. Après le déploiement, exécuter sur doctrad :

```bash
sudo bash /opt/oneforall/apps/doctrad/current/scripts/setup-oneforall-runner.sh
```

Le script détecte le service `doctrad-server`, installe le nouveau lanceur détenu
par root, conserve l'autorisation limitée à ce seul programme et exécute le
probe. Aucun accès root général ni clé SSH n'est ajouté. Après cette activation,
le lanceur se met à jour depuis le SHA exact de la release activée lors de chaque
déploiement réussi.

## Déclenchement par l'assistant

L'assistant peut créer ou modifier `.github/doctrad-automation.json` sur `main`
avec une requête bornée, par exemple :

```json
{"operation":"probe","request_id":"identifiant-unique-de-la-demande"}
```

Cela déclenche **DocTrad reference automation** sans reconstruire ni redéployer
l'application pour un simple changement de cette requête. Les valeurs permises
sont `probe`, `latest`, `run` et `status`. Un chemin de fichier, une commande ou
un identifiant de travail arbitraire ne peuvent pas être passés. Le même workflow
est aussi disponible via **Run workflow** dans GitHub.

Les fichiers reviennent dans l'artefact `doctrad-reference-ID_DU_RUN`, conservé
un jour : manifest, document source public, PDF traduit si terminé, segments,
rapport de mise en page et diagnostics. Les demandes de récupération n'utilisent
pas le navigateur et n'exigent pas le mot de passe de l'administrateur.

Une CI verte confirme les tests logiciels. Un déploiement vert confirme
l'installation par OneForAll. Un `probe` réussi avec `reference_available` et
`runtime_reachable` à `true` confirme les accès nécessaires. Un travail terminé
confirme l'exécution réelle du modèle ; la qualité visuelle et linguistique doit
encore être contrôlée dans le PDF et dans les avertissements des segments.

Les tests documentaires ne sont pas relancés automatiquement à chaque
déploiement. Il faut une demande explicite `run`, afin de respecter une pause
des essais et de ne pas occuper la BC-250 inutilement.
