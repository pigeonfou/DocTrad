# Architecture

LAN HTTPS → Nginx → FastAPI `127.0.0.1:8090` → PostgreSQL. Le worker réserve les jobs dans PostgreSQL puis analyse le document, applique mémoire/glossaire/protection et appelle le runtime `127.0.0.1:8091`. Le runtime possède une seule instance de modèle et sérialise l’inférence ainsi que les changements de poids. La clé interne est distincte de celle des sessions.

Le choix d’une file PostgreSQL évite Redis sans perdre la persistance. `SKIP LOCKED` évite une double réservation sur PostgreSQL. Une panne laisse le job en état `running` ; l’opérateur doit stopper le worker avant une récupération explicite, plutôt qu’un requeue automatique risquant de doubler un calcul long.

`app/documents.py` : formats/extraction/reconstruction ; `app/ocr.py` : OCR CPU et adaptateur Paddle ; `app/quality.py` : protection/contrôles ; `app/registry.py` : intégrité/licences/choix ; `app/translation.py` : interfaces/chargement ; `app/db.py` : persistance ; `app/web.py` : authentification/parcours ; `app/worker.py` : traitement asynchrone.

Les corrections conservent la traduction machine et un historique utilisateur/date. La mémoire est privée à chaque utilisateur. Le glossaire est global et modifiable par les administrateurs. Les jobs existants conservent `model_id` et la révision exacte, même après modification du modèle par défaut.

La première migration est une création de schéma additive via SQLAlchemy. Ce mécanisme ne remplace pas un système de migrations versionnées pour de futures modifications de colonnes. Avant une version ultérieure, ajouter Alembic et documenter la compatibilité du rollback.
