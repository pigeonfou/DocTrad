# Benchmarks

Aucun benchmark de traduction entraînée n’a été exécuté. Temps, RAM/VRAM, BLEU/chrF/COMET et qualité EN→FR : **non mesurés**. Aucun modèle recommandé, rapide ou qualité ne peut être désigné factuellement à ce stade.

`docutranslate model benchmark ID` utilise le même corpus technique de cinq phrases pour chaque modèle. Les résultats sauvegardés comprennent révision, date, OS, temps total, RSS maximal du processus runtime, conservation des données techniques et traductions. La métrique qualité reste `null` avec relecture humaine obligatoire. Les benchmarks passent par le runtime unique ; aucune seconde copie des poids n’est chargée par la CLI. Le RSS maximal est un pic de processus, pas une mesure exclusive des poids. La VRAM et les scores linguistiques ne sont pas encore instrumentés.

Si le modèle altère un placeholder, la vérification échoue. Cela peut se produire avec des tokens artificiels inconnus : évaluer les trois moteurs sur le corpus avant usage. Aucun contournement ne remplace silencieusement une vraie traduction par le texte anglais.

| Mesure | OPUS | M2M100 | MADLAD |
|---|---|---|---|
| Installé | Non | Non | Non |
| Temps | Non mesuré | Non mesuré | Non mesuré |
| RAM/VRAM | Non mesurée | Non mesurée | Non mesurée |
| Références/glossaire | Non évalués par modèle réel | Non évalués par modèle réel | Non évalués par modèle réel |
| Qualité | Non évaluée | Non évaluée | Non évaluée |
