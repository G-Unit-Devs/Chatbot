# Utiliser une image Python optimisée
FROM python:3.9-slim

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier les fichiers nécessaires
COPY . /app

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Exposer le port sur lequel Flask tourne (5000)
EXPOSE 5000

# Définir la commande de lancement de l'API
CMD ["python", "app.py"]
