import os
import json
from flask import Flask, request, jsonify, Response, render_template_string, stream_with_context
from groq import Groq

app = Flask(__name__)

API_KEY = os.environ.get("GROQ_API_KEY")
if not API_KEY:
    raise RuntimeError("GROQ_API_KEY nuk është vendosur.")

client = Groq(api_key=API_KEY)

MODEL = "openai/gpt-oss-120b"
MAX_HISTORY = 6
MAX_OUTPUT_TOKENS = 1400
MAX_MESSAGE_CHARS = 5000
MEMORY_FILE = "ghost_memory.json"

SYSTEM_PROMPT = """
You are Ghost-AI, a smart, natural, friendly AI assistant created by Matia.

PERSONALITY:
- Speak naturally and casually.
- Sound like a modern high-quality AI assistant.
- Never sound robotic, awkward, repetitive, or overly formal.
- Match the user's tone.
- Simple question = concise natural answer.
- Hard question = clear and useful explanation.
- Do not over-explain simple questions.
- Do not repeat the same phrases unnecessarily.

ALBANIAN:
- Understand Standard Albanian, Gheg, Tosk, slang, texting,
  abbreviations, spelling mistakes, missing accents and mixed English.
- When the user writes Albanian, answer naturally in Albanian.
- Understand: ca, cfar, sdi, ska, nji, bej, ma jep, ma rregullo,
  jo jo, e kam fjalen, si je, ca po ben.

NATURAL CHAT:
- User: "si je?"
- Natural answer: "Mirë jam 😄 Po ti si je?"
- Do not use awkward translated Albanian.

SMART CONTEXT:
- Use recent conversation context.
- Understand follow-up questions and references such as:
  kjo, ajo, kodi, ushtrimi, loja, versioni i fundit.
- If the user corrects you, adapt immediately.

CREATOR:
- Ghost-AI was created by Matia.
- If asked who created you, say:
  "Ghost-AI was created by Matia."

MATH:
- Be extremely accurate.
- Never guess numerical answers.
- Verify calculations.
- Solve arithmetic, percentages, fractions, algebra, equations,
  geometry, probability and statistics.
- Show useful steps when appropriate.

CODING:
- Expert in Python, JavaScript, HTML, CSS, Lua, Roblox Lua,
  CMD, PowerShell and JSON.
- Give practical copy-paste-ready code.
- Check syntax and indentation.
- Preserve working code when debugging.
- Never invent APIs or libraries.
- Never claim code was executed unless it actually was.

DEBUGGING:
- Analyze the exact error.
- Find the likely cause.
- Give a direct fix.

TUTOR:
- Explain step by step when useful.
- Match the user's level.

CREATIVE:
- Help with stories, horror stories, games, ideas, names and projects.

GENERAL:
- Never invent facts.
- If uncertain, say you are uncertain.

SAFETY:
- For cybersecurity, help only with authorized, defensive and educational uses.

IMPORTANT:
- You are Ghost-AI.
- Never claim to be ChatGPT.
"""

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_memory(items):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(items[-20:], f, ensure_ascii=False, indent=2)
    except Exception:
        pass

memory = load_memory()

def build_system_prompt():
    if memory:
        saved = "\n".join(f"- {item}" for item in memory[-8:])
    else:
        saved = "No saved memory."
    return SYSTEM_PROMPT + "\n\nRELEVANT SAVED MEMORY:\n" + saved


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ghost-AI</title>
<meta name="description" content="Ghost-AI - smart AI assistant for chat, math, coding, learning and creativity.">
<meta name="robots" content="index,follow">

<style>
*{box-sizing:border-box}
html,body{width:100%;height:100%;margin:0}
body{background:#212121;color:#ececec;font-family:Arial,Helvetica,sans-serif;overflow:hidden}
button,textarea{font-family:inherit}
.app{width:100%;height:100vh;display:flex}

.sidebar{width:270px;min-width:270px;background:#171717;border-right:1px solid #303030;display:flex;flex-direction:column}
.sidebar-top{padding:14px}
.brand{display:flex;align-items:center;gap:10px;font-size:17px;font-weight:700;margin-bottom:14px}
.logo{width:36px;height:36px;border-radius:10px;background:#10a37f;display:flex;align-items:center;justify-content:center;font-size:20px}
.new-chat{width:100%;padding:11px 12px;background:#242424;border:1px solid #414141;color:#fff;border-radius:8px;cursor:pointer;text-align:left;font-size:14px}
.new-chat:hover{background:#303030}
.history-title{padding:8px 14px 6px;color:#858585;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.chat-list{flex:1;overflow-y:auto;padding:0 8px 10px}
.empty-history{padding:12px 8px;color:#777;font-size:12px}
.chat-item{display:flex;align-items:center;gap:4px;margin-bottom:2px;border-radius:8px}
.chat-open{flex:1;min-width:0;border:0;border-radius:8px;background:transparent;color:#ddd;cursor:pointer;text-align:left;padding:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:13px}
.chat-open:hover{background:#292929}
.chat-item.active .chat-open{background:#2f2f2f;color:#fff}
.chat-delete{width:32px;height:32px;border:0;border-radius:7px;background:transparent;color:#888;cursor:pointer;opacity:0}
.chat-item:hover .chat-delete,.chat-item.active .chat-delete{opacity:1}
.chat-delete:hover{background:#3a2a2a;color:#ff8b8b}
.sidebar-bottom{padding:12px 14px;border-top:1px solid #303030;color:#888;font-size:12px;line-height:1.8}

.main{flex:1;min-width:0;display:flex;flex-direction:column}
.topbar{height:60px;flex-shrink:0;border-bottom:1px solid #303030;padding:0 18px;display:flex;align-items:center;justify-content:space-between}
.title{font-size:15px;font-weight:700}
.online{color:#10a37f;font-size:12px}

.chat{flex:1;overflow-y:auto}
.chat-inner{width:min(880px,100%);margin:0 auto;padding:28px 20px 180px}

.welcome{min-height:65vh;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center}
.welcome-logo{width:66px;height:66px;border-radius:18px;background:#10a37f;display:flex;align-items:center;justify-content:center;font-size:30px;margin-bottom:15px}
.welcome h1{margin:0 0 10px;font-size:30px}
.welcome p{max-width:520px;margin:0;color:#999;line-height:1.5}

.prompt-grid{width:min(700px,100%);display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:20px}
.prompt-button{border:1px solid #3b3b3b;border-radius:10px;background:#2a2a2a;color:#ddd;padding:13px;cursor:pointer;text-align:left;font-size:13px;transition:background .15s,transform .08s}
.prompt-button:hover{background:#333}
.prompt-button:active{transform:scale(.98)}

.message{display:flex;gap:13px;margin-bottom:28px}
.avatar{width:31px;min-width:31px;height:31px;border-radius:9px;background:#444;display:flex;align-items:center;justify-content:center}
.message.assistant .avatar{background:#10a37f}
.name{margin-bottom:5px;font-size:13px;font-weight:700}
.message.assistant .name{color:#10a37f}
.content{line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}
pre{margin:10px 0;padding:14px;overflow-x:auto;border:1px solid #333;border-radius:9px;background:#101010}
code{font-family:Consolas,"Courier New",monospace}
.copy-button{padding:6px 9px;border:1px solid #444;border-radius:6px;background:#2a2a2a;color:#ddd;cursor:pointer;font-size:12px}

.typing{display:flex;gap:5px;padding-top:5px}
.typing span{width:6px;height:6px;border-radius:50%;background:#999;animation:pulse 1.1s infinite}
.typing span:nth-child(2){animation-delay:.15s}
.typing span:nth-child(3){animation-delay:.30s}
@keyframes pulse{0%,100%{opacity:.2}50%{opacity:1}}

.composer-wrap{position:fixed;left:270px;right:0;bottom:0;padding:14px 20px 20px;background:linear-gradient(to top,#212121 72%,rgba(33,33,33,0))}
.composer{width:min(840px,100%);margin:auto;padding:8px;border:1px solid #444;border-radius:18px;background:#2f2f2f;display:flex;align-items:flex-end}
textarea{flex:1;max-height:180px;padding:9px;resize:none;outline:none;border:0;background:transparent;color:#fff;font-size:15px;line-height:1.45}
textarea::placeholder{color:#888}
.send-button{width:40px;height:40px;flex-shrink:0;border:0;border-radius:10px;background:#10a37f;color:#fff;cursor:pointer;font-size:19px}
.send-button:disabled,.new-chat:disabled{opacity:.4;cursor:default}

@media (max-width:700px){
    .sidebar{display:none}
    .composer-wrap{left:0;padding:10px}
    .chat-inner{padding-left:13px;padding-right:13px}
    .welcome h1{font-size:25px}
    .prompt-grid{grid-template-columns:1fr}
}
</style>
</head>

<body>

<div class="app">

<aside class="sidebar">

<div class="sidebar-top">

<div class="brand">
<div class="logo">👻</div>
Ghost-AI
</div>

<button id="newChatButton" class="new-chat" type="button">
＋ New chat
</button>

</div>

<div class="history-title">
Chats
</div>

<div id="chatList" class="chat-list"></div>

<div class="sidebar-bottom">
<div>● Ghost-AI Online</div>
<div>GPT-OSS 120B</div>
<div>Math Expert</div>
<div>Coding Expert</div>
<div>Smart Context</div>
<div>Memory</div>
<div>Created by Matia</div>
</div>

</aside>


<main class="main">

<header class="topbar">
<div class="title">👻 Ghost-AI</div>
<div class="online">● Online</div>
</header>


<section id="chat" class="chat">

<div id="chatInner" class="chat-inner"></div>

</section>


<div class="composer-wrap">

<div class="composer">

<textarea
id="messageInput"
rows="1"
placeholder="Message Ghost-AI..."
></textarea>

<button
id="sendButton"
class="send-button"
type="button"
>
↑
</button>

</div>

</div>

</main>

</div>


<script>

const STORAGE_KEY = "ghost_ai_chats_v6";

let chats = [];
let activeChatId = null;
let streaming = false;

const input = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const newChatButton = document.getElementById("newChatButton");
const chatList = document.getElementById("chatList");
const chat = document.getElementById("chat");
const chatInner = document.getElementById("chatInner");


function loadChats(){
    try{
        const saved = localStorage.getItem(STORAGE_KEY);
        chats = saved ? JSON.parse(saved) : [];

        if(!Array.isArray(chats)){
            chats = [];
        }
    }catch{
        chats = [];
    }
}


function saveChats(){
    try{
        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(chats)
        );
    }catch{}
}


function createId(){
    return Date.now().toString(36) +
        Math.random().toString(36).slice(2,9);
}


function makeTitle(text){

    const clean = String(text)
        .replace(/\s+/g," ")
        .trim();

    if(!clean){
        return "New chat";
    }

    return clean.length <= 38
        ? clean
        : clean.slice(0,38).trim() + "...";
}


function escapeHtml(text){
    return String(text)
        .replace(/&/g,"&amp;")
        .replace(/</g,"&lt;")
        .replace(/>/g,"&gt;")
        .replace(/"/g,"&quot;")
        .replace(/'/g,"&#039;");
}


function scrollBottom(){
    requestAnimationFrame(() => {
        chat.scrollTop = chat.scrollHeight;
    });
}


function getActiveChat(){
    return chats.find(
        item => item.id === activeChatId
    ) || null;
}


function formatAnswer(text){

    const parts = String(text).split("```");
    let html = "";

    parts.forEach((part,index)=>{

        if(index % 2 === 1){

            let lines = part.split("\n");

            if(
                lines.length > 0 &&
                /^[a-zA-Z0-9+#._-]+$/.test(
                    lines[0].trim()
                )
            ){
                lines.shift();
            }

            const code = lines.join("\n");

            html +=
                "<pre><code>" +
                escapeHtml(code) +
                "</code></pre>" +
                '<button class="copy-button" type="button">' +
                "Copy code" +
                "</button>";

        }else{

            html +=
                escapeHtml(part)
                    .replace(/\n/g,"<br>");
        }
    });

    return html;
}


function renderChatList(){

    chatList.innerHTML = "";

    if(chats.length === 0){

        const empty = document.createElement("div");
        empty.className = "empty-history";
        empty.textContent = "No chats yet.";

        chatList.appendChild(empty);

        return;
    }

    const ordered = [...chats].sort(
        (a,b) =>
            (b.updatedAt || 0) -
            (a.updatedAt || 0)
    );

    ordered.forEach(chatData=>{

        const item =
            document.createElement("div");

        item.className =
            "chat-item" +
            (
                chatData.id === activeChatId
                    ? " active"
                    : ""
            );

        const open =
            document.createElement("button");

        open.type = "button";
        open.className = "chat-open";
        open.textContent =
            chatData.title || "New chat";
        open.title =
            chatData.title || "New chat";

        open.addEventListener("click",()=>{

            if(streaming){
                return;
            }

            activeChatId = chatData.id;

            renderChatList();
            renderActiveChat();

            input.focus();
        });

        const remove =
            document.createElement("button");

        remove.type = "button";
        remove.className = "chat-delete";
        remove.textContent = "🗑";
        remove.title = "Delete chat";

        remove.addEventListener("click",event=>{

            event.stopPropagation();

            deleteChat(chatData.id);
        });

        item.appendChild(open);
        item.appendChild(remove);

        chatList.appendChild(item);
    });
}


function newChat(){

    if(streaming){
        return;
    }

    const chatData = {

        id: createId(),

        title: "New chat",

        messages: [],

        createdAt: Date.now(),

        updatedAt: Date.now()
    };

    chats.unshift(chatData);

    activeChatId =
        chatData.id;

    saveChats();
    renderChatList();
    renderActiveChat();

    input.focus();
}


function deleteChat(id){

    if(streaming){
        return;
    }

    chats =
        chats.filter(
            item => item.id !== id
        );

    if(activeChatId === id){

        activeChatId =
            chats.length > 0
                ? chats[0].id
                : null;
    }

    saveChats();

    renderChatList();
    renderActiveChat();
}


function renderWelcome(){

    chatInner.innerHTML = `
        <div id="welcome" class="welcome">

            <div class="welcome-logo">
                👻
            </div>

            <h1>
                How can I help?
            </h1>

            <p>
                Chat, math, coding, learning and creativity.
            </p>

            <div class="prompt-grid">

                <button
                    class="prompt-button"
                    type="button"
                    data-prompt="Me krijo një histori horror shumë interesante me një twist në fund."
                >
                    👻 Horror story
                </button>

                <button
                    class="prompt-button"
                    type="button"
                    data-prompt="Zgjidh 3x + 7 = 25 dhe ma shpjego hap pas hapi."
                >
                    🧮 Math
                </button>

                <button
                    class="prompt-button"
                    type="button"
                    data-prompt="Me krijo një mini game të plotë në JavaScript me coins, enemies, score dhe game over."
                >
                    💻 JavaScript Game
                </button>

                <button
                    class="prompt-button"
                    type="button"
                    data-prompt="Ma shpjego Black Hole në mënyrë interesante dhe të kuptueshme."
                >
                    🌌 Black Hole
                </button>

            </div>
        </div>
    `;
}


function renderActiveChat(){

    chatInner.innerHTML = "";

    const active =
        getActiveChat();

    if(
        !active ||
        !Array.isArray(active.messages) ||
        active.messages.length === 0
    ){

        renderWelcome();
        return;
    }

    active.messages.forEach(message=>{

        addMessageToUI(
            message.role,
            message.content
        );
    });

    scrollBottom();
}


function wireCopyButtons(container){

    container
        .querySelectorAll(".copy-button")
        .forEach(button=>{

            button.addEventListener(
                "click",
                async ()=>{

                    const pre =
                        button.previousElementSibling;

                    if(!pre){
                        return;
                    }

                    try{

                        await navigator.clipboard.writeText(
                            pre.innerText
                        );

                        button.textContent =
                            "Copied!";

                        setTimeout(()=>{
                            button.textContent =
                                "Copy code";
                        },1000);

                    }catch{

                        button.textContent =
                            "Copy failed";
                    }
                }
            );
        });
}


function addMessageToUI(role,text){

    const message =
        document.createElement("div");

    message.className =
        "message " + role;

    const isAI =
        role === "assistant";

    message.innerHTML = `
        <div class="avatar">
            ${isAI ? "👻" : "M"}
        </div>

        <div style="flex:1">

            <div class="name">
                ${isAI ? "Ghost-AI" : "You"}
            </div>

            <div class="content">
                ${
                    isAI
                        ? formatAnswer(text)
                        : escapeHtml(text)
                            .replace(/\n/g,"<br>")
                }
            </div>

        </div>
    `;

    chatInner.appendChild(message);

    wireCopyButtons(message);
}


function createStreamingMessage(){

    const message =
        document.createElement("div");

    message.className =
        "message assistant";

    message.innerHTML = `
        <div class="avatar">
            👻
        </div>

        <div style="flex:1">

            <div class="name">
                Ghost-AI
            </div>

            <div
                class="content"
                id="streamContent"
            ></div>

        </div>
    `;

    chatInner.appendChild(message);

    return {
        root: message,
        content:
            message.querySelector(
                "#streamContent"
            )
    };
}


async function sendMessage(customText = null){

    if(streaming){
        return;
    }

    let active =
        getActiveChat();

    if(!active){

        newChat();

        active =
            getActiveChat();
    }

    const text = (
        customText !== null
            ? String(customText)
            : input.value
    ).trim();

    if(!text){
        return;
    }

    streaming = true;

    sendButton.disabled = true;
    newChatButton.disabled = true;

    input.value = "";
    input.style.height = "auto";

    if(active.messages.length === 0){
        active.title =
            makeTitle(text);
    }

    active.messages.push({
        role: "user",
        content: text
    });

    active.updatedAt =
        Date.now();

    saveChats();

    renderChatList();
    renderActiveChat();

    const streamUI =
        createStreamingMessage();

    let fullAnswer = "";

    const recent =
        active.messages.slice(
            -MAX_HISTORY
        );

    try{

        const response =
            await fetch(
                "/api/chat/stream",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            messages:
                                recent
                        })
                }
            );

        if(!response.ok){

            let errorMessage =
                "Server error.";

            try{

                const data =
                    await response.json();

                errorMessage =
                    data.error ||
                    errorMessage;

            }catch{}

            throw new Error(
                errorMessage
            );
        }

        if(!response.body){

            throw new Error(
                "Streaming is not supported by this browser."
            );
        }

        const reader =
            response.body.getReader();

        const decoder =
            new TextDecoder();

        let buffer = "";

        while(true){

            const result =
                await reader.read();

            if(result.done){
                break;
            }

            buffer +=
                decoder.decode(
                    result.value,
                    {stream:true}
                );

            const packets =
                buffer.split("\n\n");

            buffer =
                packets.pop() || "";

            for(
                const packet of packets
            ){

                const line =
                    packet
                        .split("\n")
                        .find(
                            value =>
                                value.startsWith(
                                    "data: "
                                )
                        );

                if(!line){
                    continue;
                }

                const payload =
                    line.slice(6);

                if(payload === "[DONE]"){
                    continue;
                }

                let parsed;

                try{

                    parsed =
                        JSON.parse(
                            payload
                        );

                }catch{

                    continue;
                }

                if(parsed.type === "delta"){

                    fullAnswer +=
                        parsed.content || "";

                    streamUI.content.textContent =
                        fullAnswer;

                    scrollBottom();
                }

                if(parsed.type === "error"){

                    throw new Error(
                        parsed.message ||
                        "AI error."
                    );
                }
            }
        }

        if(!fullAnswer){

            fullAnswer =
                "Nuk mora përgjigje.";
        }

        active.messages.push({
            role: "assistant",
            content: fullAnswer
        });

        active.updatedAt =
            Date.now();

        saveChats();

        streamUI.root.remove();

        addMessageToUI(
            "assistant",
            fullAnswer
        );

        renderChatList();
        scrollBottom();

    }catch(error){

        streamUI.root.remove();

        const errorText =
            "⚠️ " +
            (
                error.message ||
                "Nuk u lidh dot me Ghost-AI."
            );

        active.messages.push({
            role: "assistant",
            content: errorText
        });

        active.updatedAt =
            Date.now();

        saveChats();

        renderActiveChat();

    }finally{

        streaming = false;

        sendButton.disabled = false;
        newChatButton.disabled = false;

        input.focus();
    }
}


sendButton.addEventListener(
    "click",
    () => sendMessage()
);

newChatButton.addEventListener(
    "click",
    () => newChat()
);

input.addEventListener(
    "keydown",
    event => {

        if(
            event.key === "Enter" &&
            !event.shiftKey
        ){

            event.preventDefault();

            sendMessage();
        }
    }
);

input.addEventListener(
    "input",
    function(){

        this.style.height = "auto";

        this.style.height =
            Math.min(
                this.scrollHeight,
                180
            ) + "px";
    }
);

document.addEventListener(
    "click",
    event => {

        const button =
            event.target.closest(
                ".prompt-button"
            );

        if(!button){
            return;
        }

        const prompt =
            button.getAttribute(
                "data-prompt"
            );

        if(prompt){
            sendMessage(prompt);
        }
    }
);

loadChats();

if(chats.length > 0){
    activeChatId =
        chats[0].id;
}

renderChatList();
renderActiveChat();

input.focus();

</script>

</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "app": "Ghost-AI",
        "model": MODEL
    })


@app.route("/api/chat", methods=["POST"])
def chat_api():

    try:

        data =
            request.get_json(
                silent=True
            )

        if not isinstance(data, dict):
            return jsonify({
                "error": "Invalid request."
            }), 400

        incoming =
            data.get(
                "messages",
                []
            )

        if not isinstance(incoming, list):
            return jsonify({
                "error": "Invalid messages."
            }), 400

        recent =
            incoming[-MAX_HISTORY:]

        request_messages = [
            {
                "role":
                    "system",
                "content":
                    build_system_prompt()
            }
        ]

        for item in recent:

            if not isinstance(item, dict):
                continue

            role =
                item.get("role")

            content =
                item.get("content")

            if role not in (
                "user",
                "assistant"
            ):
                continue

            if not isinstance(content, str):
                continue

            request_messages.append({
                "role":
                    role,
                "content":
                    content[
                        :MAX_MESSAGE_CHARS
                    ]
            })

        if len(request_messages) < 2:
            return jsonify({
                "error":
                    "No user message."
            }), 400

        response =
            client.chat.completions.create(
                model=MODEL,
                messages=request_messages,
                temperature=0.5,
                top_p=0.9,
                max_completion_tokens=MAX_OUTPUT_TOKENS
            )

        answer =
            response.choices[
                0
            ].message.content or "Nuk mora përgjigje."

        return jsonify({
            "answer":
                answer
        })

    except Exception as error:

        return jsonify({
            "error":
                str(error)
        }), 500


@app.route(
    "/api/chat/stream",
    methods=["POST"]
)
def chat_stream():

    try:

        data =
            request.get_json(
                silent=True
            )

        if not isinstance(data, dict):
            return jsonify({
                "error":
                    "Invalid request."
            }), 400

        incoming =
            data.get(
                "messages",
                []
            )

        if not isinstance(incoming, list):
            return jsonify({
                "error":
                    "Invalid messages."
            }), 400

        recent =
            incoming[-MAX_HISTORY:]

        request_messages = [
            {
                "role":
                    "system",
                "content":
                    build_system_prompt()
            }
        ]

        for item in recent:

            if not isinstance(item, dict):
                continue

            role =
                item.get("role")

            content =
                item.get("content")

            if role not in (
                "user",
                "assistant"
            ):
                continue

            if not isinstance(content, str):
                continue

            request_messages.append({
                "role":
                    role,
                "content":
                    content[
                        :MAX_MESSAGE_CHARS
                    ]
            })

        if len(request_messages) < 2:
            return jsonify({
                "error":
                    "No user message."
            }), 400

        if request_messages[-1]["role"] != "user":
            return jsonify({
                "error":
                    "Last message must be from user."
            }), 400

    except Exception as error:

        return jsonify({
            "error":
                str(error)
        }), 400


    @stream_with_context
    def generate():

        try:

            stream =
                client.chat.completions.create(
                    model=MODEL,
                    messages=request_messages,
                    temperature=0.5,
                    top_p=0.9,
                    max_completion_tokens=MAX_OUTPUT_TOKENS,
                    stream=True
                )

            for chunk in stream:

                if not chunk.choices:
                    continue

                delta =
                    chunk.choices[
                        0
                    ].delta.content

                if delta:

                    payload =
                        json.dumps(
                            {
                                "type":
                                    "delta",
                                "content":
                                    delta
                            },
                            ensure_ascii=False
                        )

                    yield (
                        "data: " +
                        payload +
                        "\n\n"
                    )

            yield "data: [DONE]\n\n"

        except Exception as error:

            payload =
                json.dumps(
                    {
                        "type":
                            "error",
                        "message":
                            str(error)
                    },
                    ensure_ascii=False
                )

            yield (
                "data: " +
                payload +
                "\n\n"
            )


    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":
                "no-cache",
            "X-Accel-Buffering":
                "no",
            "Connection":
                "keep-alive"
        }
    )


@app.route(
    "/api/memory",
    methods=["GET"]
)
def get_memory():

    return jsonify({
        "memory":
            memory
    })


@app.route(
    "/api/memory",
    methods=["POST"]
)
def add_memory():

    global memory

    data =
        request.get_json(
            silent=True
        ) or {}

    text =
        str(
            data.get(
                "text",
                ""
            )
        ).strip()

    if not text:

        return jsonify({
            "error":
                "Memory is empty."
        }), 400

    memory.append(text)

    save_memory(memory)

    return jsonify({
        "ok":
            True
    })


@app.route(
    "/api/memory",
    methods=["DELETE"]
)
def clear_memory():

    global memory

    memory = []

    save_memory(memory)

    return jsonify({
        "ok":
            True
    })


if __name__ == "__main__":

    port =
        int(
            os.environ.get(
                "PORT",
                "5000"
            )
        )

    print("======================================")
    print("          GHOST-AI ONLINE")
    print("======================================")
    print("MODEL:", MODEL)
    print("PORT:", port)
    print("======================================")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
