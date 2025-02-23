from flask import Flask, request, jsonify
from flask_swagger_ui import get_swaggerui_blueprint
import ollama
import json
from flask_cors import CORS
import os
from langdetect import detect, DetectorFactory

# Assure une détection de langue stable
DetectorFactory.seed = 0

app = Flask(__name__)
CORS(app)

# Configuration de Swagger UI
SWAGGER_URL = '/api/docs'  # URL pour accéder à l'interface Swagger UI
API_URL = '/static/swagger.json'  # URL du fichier Swagger JSON

# Créer un blueprint pour Swagger UI
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Chatbot API"
    }
)

# Enregistrer le blueprint dans l'application Flask
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

DATA_FILE = "user_data.json"

# Champs collectables en fonction du rôle
COLLECTABLE_FIELDS = {
    "pro": ["domain", "experience", "help", "expectations", "about", "histoires", "passions"],
    "chercheur": ["expectations", "about", "histoires", "centres_interets"]
}

# Domaines liés à la tech
TECH_DOMAINS = [
    "tech", "technologie", "informatique", "développement", "programmation", "data science", 
    "intelligence artificielle", "IA", "machine learning", "cybersécurité", "cloud computing", 
    "réseaux", "devops", "ingénierie logicielle", "robotique", "IoT", "blockchain"
]

def detect_language(text):
    """Détecte la langue avec langdetect et force le français si des mots-clés français sont détectés."""
    french_keywords = ["bonjour", "salut", "merci", "oui", "non"]
    if any(keyword in text.lower() for keyword in french_keywords):
        return "fr"
    try:
        lang = detect(text)
        return "fr" if lang == "fr" else "en"
    except:
        return "en"

def is_tech_related(domain):
    """Vérifie si le domaine est lié à la tech."""
    return any(tech_domain in domain.lower() for tech_domain in TECH_DOMAINS)

# def load_user_data():
#     """Charge les données utilisateur depuis le fichier JSON."""
#     if not os.path.exists(DATA_FILE):
#         return []
#     with open(DATA_FILE, "r") as f:
#         try:
#             return json.load(f)
#         except json.JSONDecodeError:
#             return []

# def save_user_data(data):
#     """Sauvegarde les données utilisateur dans le fichier JSON."""
#     with open(DATA_FILE, "w") as f:
#         json.dump(data, f, indent=4)

def analyze_with_llm(user_message, role, existing_data, language, conversation_history):
    """Utilise le LLM pour analyser le message, extraire les informations et générer une réponse."""
    # Définir les champs à collecter en fonction du rôle
    required_fields = COLLECTABLE_FIELDS.get(role, [])

    # Générer un prompt pour le LLM
    prompt = (
        f"Tu te nomme Paris, un assistant IA conçu pour collecter des informations clés tout en maintenant une conversation naturelle.\n"
        f"### Mission :\n"
        f"1. Collecter les informations suivantes : {', '.join(required_fields)}.\n"
        f"2. Maintenir une conversation fluide et engageante.\n"
        f"3. Adapter tes réponses en fonction de l'état d'esprit de l'utilisateur.\n"
        f"4. Rebondir sur la réponse de l'utilisateur pour poser une question connexe.\n"
        f"5. Ne jamais poser deux fois la même question.\n"
        f"6. La plateforme est centrée sur la tech. Si l'utilisateur ne travaille pas dans un domaine lié à la tech, explique-lui gentiment que la plateforme est réservée aux professionnels et chercheurs dans ce domaine.\n\n"
        f"### Contexte :\n"
        f"Rôle de l'utilisateur : {role}\n"
        f"Langue : {language}\n"
        f"Informations déjà collectées : {json.dumps(existing_data, ensure_ascii=False)}\n"
        f"Historique de la conversation : {json.dumps(conversation_history, ensure_ascii=False)}\n\n"
        f"### Message de l'utilisateur :\n"
        f"'{user_message}'\n\n"
        f"### Instructions :\n"
        f"1. Analyse le message de l'utilisateur pour identifier les informations pertinentes.\n"
        f"2. Si une information manquante est mentionnée, enregistre-la dans un JSON sous la clé 'data'.\n"
        f"3. Génère une réponse naturelle et contextuelle pour engager la conversation.\n"
        f"4. Si l'utilisateur exprime une émotion (frustration, ennui, etc.), réponds avec empathie.\n"
        f"5. Si l'utilisateur ne travaille pas dans un domaine lié à la tech, explique-lui gentiment que la plateforme est réservée aux professionnels et chercheurs dans ce domaine.\n"
        f"6. Réponds UNIQUEMENT en {language}.\n"
        f"7. Retourne un JSON au format suivant :\n"
        "{ \"data\": { \"field1\": \"value1\", \"field2\": \"value2\" }, \"response\": \"Ta réponse ici\" }"
    )

    # Envoyer le prompt au LLM
    response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])

    try:
        # Extraire la réponse du LLM
        extracted_data = json.loads(response['message']['content'])
        if not isinstance(extracted_data, dict) or "response" not in extracted_data:
            raise ValueError("Invalid JSON format from model")

        # Mettre à jour les données existantes avec les nouvelles informations
        extracted_data["data"] = {**existing_data, **extracted_data.get("data", {})}

    except (json.JSONDecodeError, ValueError):
        # En cas d'erreur, retourner une réponse générique
        extracted_data = {
            "data": existing_data,
            "response": "Je n'ai pas bien compris, peux-tu reformuler ?" if language == "fr" else "I didn't quite understand, could you rephrase?"
        }

    return extracted_data

@app.route("/chat", methods=["POST"])
def chat():
    """
    Endpoint pour interagir avec le chatbot.
    ---
    tags:
      - Chatbot
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            message:
              type: string
              description: Le message de l'utilisateur.
            role:
              type: string
              description: Le rôle de l'utilisateur (pro ou chercheur).
    responses:
      200:
        description: Réponse du chatbot.
        schema:
          type: object
          properties:
            response:
              type: string
              description: La réponse du chatbot.
      400:
        description: Erreur si le message ou le rôle est manquant ou invalide.
    """
    data = request.json
    user_message = data.get("message", "")
    user_role = data.get("role", "")
    user_data = data.get("trajectory", "")
    user_history = data.get("history", "")

    # print(data);

    if not user_message or user_role not in ["pro", "chercheur"]:
        return jsonify({"error": "Message vide ou rôle non reconnu."}), 400

    #existing_data_list = user_data
    #print(existing_data_list);
    #user_entry = next((entry for entry in existing_data_list if entry["role"] == user_role), None)
    user_entry = user_data;

    # Détecter la langue une seule fois au début, et la garder fixe
    """ if user_entry is None:
        language = detect_language(user_message)
        user_entry = {"role": user_role, "language": language, "data": {}, "conversation_history": []}
        existing_data_list = user_data if isinstance(user_data, list) else []
        existing_data_list.append(user_entry)
        if isinstance(existing_data_list, list):
            existing_data_list.append(user_entry)
    else:
        language = user_entry["language"] """
    language= "fr";

    existing_data = user_entry.get("data", {})
    conversation_history = user_history

    # Ajouter le message de l'utilisateur à l'historique
    conversation_history.append({"role": "user", "content": user_message})

    # Analyser le message avec le modèle LLM
    extracted_data = analyze_with_llm(user_message, user_role, existing_data, language, conversation_history)

    # Mettre à jour les données et l'historique
    user_entry["data"] = extracted_data["data"]
    user_entry["conversation_history"] = conversation_history
    print(conversation_history)

    # # Sauvegarder les données mises à jour
    # save_user_data(existing_data_list)

    # Générer la réponse du bot
    bot_response = extracted_data.get("response", "Je n'ai pas bien compris, peux-tu reformuler ?" if language == "fr" else "I didn't quite understand, could you rephrase?")

    # Ajouter la réponse du bot à l'historique
    conversation_history.append({"role": "bot", "content": bot_response})

    return jsonify({"response": bot_response, "trajectory": user_entry.get('data'), language: language})

@app.route("/greetings", methods=["GET"])
def greetings():
    """
    Endpoint pour générer dynamiquement un message de bienvenue avec Ollama.
    ---
    tags:
      - Messages
    responses:
      200:
        description: Message de bienvenue généré par le LLM.
        schema:
          type: object
          properties:
            message:
              type: string
              description: Le message de bienvenue généré.
    """
    # Générer une demande au modèle LLM
    prompt = (
        "Génère un message de bienvenue chaleureux et engageant pour un nouvel utilisateur "
        "qui vient d'arriver sur le site. Le message doit être naturel et amical."
        "Incite l'utilisateur à se présenter, présenter ses attentes ou poser des questions s'il le souhaite."
        "Le message doit être adapté à un public francophone."
        "soit court et concis, mais suffisamment informatif pour encourager l'utilisateur à interagir."
    )

    try:
        # Appel à Ollama pour générer un message
        response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])

        # Extraire la réponse générée
        generated_message = response['message']['content'].strip()

    except Exception as e:
        generated_message = "Bienvenue sur notre plateforme ! Nous sommes ravis de vous accueillir. 😊"

    return jsonify({"message": generated_message})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)