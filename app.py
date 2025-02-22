from flask import Flask, request, jsonify
import ollama
import json
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

DATA_FILE = "user_data.json"

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

def analyze_with_llm(user_message, role, existing_data, language):
    """Analyse le message utilisateur avec le modèle LLM pour extraire les informations manquantes."""
    if role == "pro":
        prompt = (
            f"You are an AI assistant designed to extract key user information for matchmaking.\n"
            f"User role: {role}\n"
            f"Langue: {language}\n"
            f"Existing stored information: {json.dumps(existing_data, ensure_ascii=False)}\n"
            f"User message: '{user_message}'\n\n"
            "### Instructions:\n"
            "1. Identify and extract only missing details (domain, experience, help, expectations, about) WITHOUT modifying already stored information.\n"
            "2. If all necessary information is collected, transition to free conversation.\n"
            "3. NEVER mix languages in responses. Respond strictly in {language}.\n"
            "4. STRICTLY return a JSON response in this format:\n"
            "5. Respond STRICTLY in {language}. If the detected language is French, your response must be in French."
            "{ \"role\": \"pro\", \"data\": { \"domain\": \"existing or new value\", \"experience\": \"existing or new value\", \"help\": \"existing or new value\", \"expectations\": \"existing or new value\", \"about\": \"existing or new value\" }, \"response\": \"Your response here\" }"
        )
    elif role == "chercheur":
        prompt = (
            f"You are an AI assistant designed to extract key user information for matchmaking.\n"
            f"User role: {role}\n"
            f"Detected language: {language}\n"
            f"Existing stored information: {json.dumps(existing_data, ensure_ascii=False)}\n"
            f"User message: '{user_message}'\n\n"
            "### Instructions:\n"
            "1. Identify and extract only missing details (expectations, about) WITHOUT modifying already stored information.\n"
            "2. If all necessary information is collected, transition to free conversation.\n"
            "3. NEVER mix languages in responses. Respond strictly in {language}.\n"
            "4. STRICTLY return a JSON response in this format:\n"
            "{ \"role\": \"chercheur\", \"data\": { \"expectations\": \"existing or new value\", \"about\": \"existing or new value\" }, \"response\": \"Your response here\" }"
        )
    else:
        return {"role": role, "data": existing_data, "response": "Rôle non reconnu." if language == "fr" else "Role not recognized."}
    
    response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
    
    try:
        extracted_data = json.loads(response['message']['content'])
        if not isinstance(extracted_data, dict) or "response" not in extracted_data:
            raise ValueError("Invalid JSON format from model")
        extracted_data["role"] = role  # Ensure the correct role is saved
        extracted_data["language"] = language  # Preserve language consistency
        
        # Ensure missing fields are updated but existing ones remain unchanged
        for key, value in existing_data.items():
            if key in extracted_data["data"] and not extracted_data["data"][key]:
                extracted_data["data"][key] = value
    except (json.JSONDecodeError, ValueError):
        extracted_data = {"role": role, "data": existing_data, "response": "Je n'ai pas bien compris, peux-tu reformuler ?" if language == "fr" else "I didn't quite understand, could you rephrase?"}
    
    return extracted_data

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "")
    user_role = data.get("role", "")
    
    if not user_message or user_role not in ["pro", "chercheur"]:
        return jsonify({"error": "Message vide ou rôle non reconnu." if any(ord(c) > 127 for c in user_message) else "Empty message or unrecognized role."}), 400
    
    # Detect language
    language = "fr" if any(ord(c) > 127 for c in user_message) else "en"
    
    # Load existing stored data
    existing_data_list = load_user_data()
    existing_data = next((entry["data"] for entry in existing_data_list if entry["role"] == user_role and entry.get("language") == language), {})
    
    # Analyze with LLM
    extracted_data = analyze_with_llm(user_message, user_role, existing_data, language)
    
    # Ensure role consistency
    extracted_data["role"] = user_role
    
    # Update and save new data without overwriting existing information
    updated_entry = {"role": user_role, "language": language, "data": extracted_data["data"], "response": extracted_data["response"]}
    
    # Update the existing data list
    existing_data_list = [entry for entry in existing_data_list if not (entry["role"] == user_role and entry.get("language") == language)]
    existing_data_list.append(updated_entry)
    
    save_user_data(existing_data_list)
    
    # Generate relevant and fluid response, preserving language
    bot_response = extracted_data.get("response", "Peux-tu préciser un point manquant pour compléter ton profil ?" if language == "fr" else "Can you provide more details to complete your profile?")
    
    return jsonify({"response": bot_response})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)