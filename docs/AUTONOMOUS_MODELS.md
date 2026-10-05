# Installation autonome des modèles

Après les tests locaux et un déploiement réussi, le workflow `DocTrad local model`
installe le modèle déclaré dans `packaging/models/default.json`, vérifie son
intégrité, le définit par défaut et exécute le benchmark technique.
Le téléchargement est une préparation explicitement connectée ; les services
de traduction conservent leur configuration hors ligne.

Une activation administrateur unique est nécessaire sur les serveurs déjà
installés : récupérer le dépôt puis exécuter `scripts/setup-github-deployment.sh`
avec sudo. Le runner n'obtient aucun droit sudo général. La commande installée
accepte uniquement un SHA complet correspondant à la release active ; le modèle
doit appartenir à la liste autorisée et sa révision doit être exacte. Les poids
sont préparés sous le compte applicatif, dans un dossier temporaire. Une erreur
de téléchargement ne laisse pas de modèle partiel dans le registre.

Une installation existante est vérifiée et conservée. Un changement de révision
pour le même identifiant demande une revue administrateur et n'écrase pas les
poids existants. Le benchmark reste une vérification technique et demande une
revue humaine de la qualité linguistique. L'installation réelle du modèle n'est
pas validée tant que le workflow ne réussit pas.
