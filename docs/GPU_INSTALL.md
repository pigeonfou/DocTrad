# GPU NVIDIA

Le CPU est le mode par défaut ; aucune carte n’est requise. Le lock testé contient PyTorch avec bibliothèques CUDA, mais le test CPU a fonctionné sans GPU. Ce lock est volumineux ; un lock CPU dédié reste à préparer et tester avant une distribution légère.

Pour un serveur GPU, installer un pilote Ubuntu/NVIDIA compatible avec la version CUDA de PyTorch sur une machine de validation. Ne pas modifier aveuglément un pilote fonctionnel. Contrôler `nvidia-smi`, puis `torch.cuda.is_available()` et une vraie inférence.

Changer `device` du manifest en `cuda` seulement après ce test ; le moteur refuse CUDA si indisponible. Le runtime sérialise les appels : une seule inférence concurrente. FP32 est actuellement la précision implémentée. FP16/BF16/INT8 et les autres quantifications ne sont pas validées.

Aucun GPU disponible dans l’environnement de réalisation. L’accélération, la consommation VRAM, les limites systemd avec CUDA et la préparation hors ligne des pilotes ne sont pas validées. Préparer les DEB du pilote avec leurs dépendances sur un Ubuntu de même version et tester le redémarrage isolé.
