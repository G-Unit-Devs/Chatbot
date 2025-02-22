from flask import Flask, request, jsonify
import ollama
import json
from flask_cors import CORS
import os
from langdetect import detect, DetectorFactory

# Assure une détection de langue stable
DetectorFactory.seed = 0

app = Flask(__name__)
CORS(app)

DATA_FILE = "user_data.json"
COLLECTABLE_FIELDS = ["domain", "experience", "help", "expectations", "about"]

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

def load_user_data():
    """Charge les données utilisateur depuis le fichier JSON."""
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_user_data(data):
    """Sauvegarde les données utilisateur dans le fichier JSON."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def analyze_with_llm(user_message, role, existing_data, language, conversation_history):
    """Utilise le LLM pour analyser le message, extraire les informations et générer une réponse."""
    # Générer un prompt pour le LLM
    prompt = (
        f"Tu es un assistant IA conçu pour collecter des informations clés tout en maintenant une conversation naturelle.\n"
        f"### Mission :\n"
        f"1. Collecter les informations suivantes : {', '.join(COLLECTABLE_FIELDS)}.\n"
        f"2. Maintenir une conversation fluide et engageante.\n"
        f"3. Adapter tes réponses en fonction de l'état d'esprit de l'utilisateur.\n"
        f"4. Ne jamais poser deux fois la même question.\n\n"
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
        f"5. Réponds UNIQUEMENT en {language}.\n"
        f"6. Retourne un JSON au format suivant :\n"
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
    data = request.json
    user_message = data.get("message", "")
    user_role = data.get("role", "")

    if not user_message or user_role not in ["pro", "chercheur"]:
        return jsonify({"error": "Message vide ou rôle non reconnu."}), 400

    existing_data_list = load_user_data()
    user_entry = next((entry for entry in existing_data_list if entry["role"] == user_role), None)

    # Détecter la langue une seule fois au début, et la garder fixe
    if user_entry is None:
        language = detect_language(user_message)
        user_entry = {"role": user_role, "language": language, "data": {}, "conversation_history": []}
        existing_data_list.append(user_entry)
    else:
        language = user_entry["language"]

    existing_data = user_entry.get("data", {})
    conversation_history = user_entry.get("conversation_history", [])

    # Ajouter le message de l'utilisateur à l'historique
    conversation_history.append({"role": "user", "content": user_message})

    # Analyser le message avec le modèle LLM
    extracted_data = analyze_with_llm(user_message, user_role, existing_data, language, conversation_history)

    # Mettre à jour les données et l'historique
    user_entry["data"] = extracted_data["data"]
    user_entry["conversation_history"] = conversation_history

    # Sauvegarder les données mises à jour
    save_user_data(existing_data_list)

    # Générer la réponse du bot
    bot_response = extracted_data.get("response", "Je n'ai pas bien compris, peux-tu reformuler ?" if language == "fr" else "I didn't quite understand, could you rephrase?")

    # Ajouter la réponse du bot à l'historique
    conversation_history.append({"role": "bot", "content": bot_response})

    return jsonify({"response": bot_response})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)