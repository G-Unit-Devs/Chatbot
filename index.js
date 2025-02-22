// index.js

let role = "";
let userData = {};

document.addEventListener("DOMContentLoaded", function() {
    document.getElementById("pro-btn").addEventListener("click", () => startChat("pro"));
    document.getElementById("chercheur-btn").addEventListener("click", () => startChat("chercheur"));
    document.getElementById("send-btn").addEventListener("click", sendMessage);
});

function startChat(selectedRole) {
    role = selectedRole;
    userData = { role: selectedRole, responses: [] };
    document.getElementById('chat-container').style.display = 'block';
    document.getElementById('role-selection').style.display = 'none';
    addMessage("bot", "Bienvenue ! Discutons de tech et de votre parcours. Commencer par vous présentez.");
}

function addMessage(sender, message) {
    let chatbox = document.getElementById("chatbox");
    let msgDiv = document.createElement("div");
    msgDiv.textContent = sender + ": " + message;
    chatbox.appendChild(msgDiv);
    chatbox.scrollTop = chatbox.scrollHeight;
}

async function sendMessage() {
    let input = document.getElementById("userInput");
    let message = input.value.trim();
    if (message) {
        addMessage("Vous", message);
        input.value = "";
        
        try {
            let response = await fetch("http://127.0.0.1:5000/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: message, role: role })
            });
            let data = await response.json();
            addMessage("bot", data.response);
        } catch (error) {
            addMessage("bot", "Erreur de connexion avec le serveur");
        }
    }
}
