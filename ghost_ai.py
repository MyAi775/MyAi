import os
import json
import re
from flask import Flask, request, jsonify, Response, render_template_string, stream_with_context
from groq import Groq

app = Flask(__name__)

# ============================================================
# CONFIG
# ============================================================

API_KEY = os.environ.get("GROQ_API_KEY")

if not API_KEY:
    raise RuntimeError("GROQ_API_KEY nuk është vendosur në Render Environment Variables.")

client = Groq(api_key=API_KEY)

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

MAX_HISTORY = 10
MAX_OUTPUT_TOKENS = 1800
MAX_MESSAGE_CHARS = 6000
MAX_MEMORY_ITEMS = 30

MEMORY_FILE = "ghost_memory.json"


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are Ghost-AI, a smart, natural, friendly AI assistant created by Matia.

IDENTITY:
- Your name is Ghost-AI.
- You were created by Matia.
- If asked who created you, say: "Ghost-AI was created by Matia."
- Never claim to be ChatGPT.

PERSONALITY:
- Friendly, natural and intelligent.
- Match the user's language and tone.
- If the user speaks Albanian, answer naturally in Albanian.
- Understand Albanian slang, abbreviations and mistakes.
- Understand phrases such as:
  ca, cfar, sdi, ska, nji, ma jep, beje, rregulloje,
  jo jo, e kam fjalen, pse, si ta bej.
- Do not sound robotic.
- Do not unnecessarily repeat yourself.
- Simple question = concise answer.
- Difficult question = useful explanation.

SMART CONTEXT:
- Use previous messages to understand references.
- Understand "kjo", "ajo", "kodi", "scripti", "versioni i fundit",
  "ai", "problemi", "errori" and similar references.
- If the user corrects you, adapt immediately.

MEMORY:
- Use relevant saved memory when available.
- Never invent memories.
- Never pretend something was saved if it was not.

MATH EXPERT:
- Solve arithmetic, percentages, fractions, algebra,
  equations, geometry, probability and statistics.
- Be extremely accurate.
- Verify calculations before answering.
- Show steps when useful.

CODING EXPERT:
- Expert in Python, JavaScript, HTML, CSS, JSON,
  Lua, Roblox Lua, CMD and PowerShell.
- Give copy-paste-ready code.
- Check syntax and indentation.
- When debugging, focus on the exact error.
- Preserve existing functionality whenever possible.
- Never claim code was executed unless it actually was.

TUTOR:
- Explain things step by step.
- Adapt explanations to the user's level.
- Make difficult subjects easier.

QUIZ:
- Can create quizzes about football, science, coding,
  mathematics, gaming, geography and general knowledge.
- Ask one question at a time when appropriate.
- Track the score during the current conversation.

CREATIVE:
- Help with stories, games, names, ideas, projects,
  websites and creative concepts.

WEB / CURRENT INFORMATION:
- Do not pretend to have live web access.
- If something requires current information, say that it may need verification.

CYBERSECURITY:
- Help with authorized, defensive and educational cybersecurity.
- Do not assist with stealing passwords, unauthorized access,
  malware or harming systems.

IMPORTANT:
- Answer the actual user request.
- Do not invent facts.
"""


# ============================================================
# MEMORY
# ============================================================

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data[-MAX_MEMORY_ITEMS:]

    except Exception:
        pass

    return []


def save_memory(items):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as file:
            json.dump(
                items[-MAX_MEMORY_ITEMS:],
                file,
                ensure_ascii=False,
                indent=2
            )
    except Exception:
        pass


memory = load_memory()


def build_system_prompt():
    if memory:
        saved_memory = "\n".join(
            "- " + str(item)
            for item in memory[-10:]
        )
    else:
        saved_memory = "No saved memory."

    return (
        SYSTEM_PROMPT
        + "\n\nRELEVANT SAVED MEMORY:\n"
        + saved_memory
    )


# ============================================================
# MESSAGE VALIDATION
# ============================================================

def build_messages(incoming):
    if not isinstance(incoming, list):
        raise ValueError("Invalid messages.")

    recent = incoming[-MAX_HISTORY:]

    messages = [
        {
            "role": "system",
            "content": build_system_prompt()
        }
    ]

    for item in recent:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role not in ("user", "assistant"):
            continue

        if not isinstance(content, str):
            continue

        content = content[:MAX_MESSAGE_CHARS]

        if not content.strip():
            continue

        messages.append(
            {
                "role": role,
                "content": content
            }
        )

    if len(messages) < 2:
        raise ValueError("No user message.")

    return messages


# ============================================================
# HTML
# ============================================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>Ghost-AI</title>

<meta
    name="description"
    content="Ghost-AI smart assistant"
>

<style>

* {
    box-sizing: border-box;
}

html,
body {
    width: 100%;
    height: 100%;
    margin: 0;
}

body {
    background: #212121;
    color: #ececec;
    font-family: Arial, Helvetica, sans-serif;
    overflow: hidden;
}

button,
textarea {
    font-family: inherit;
}

.app {
    width: 100%;
    height: 100vh;
    display: flex;
}

/* SIDEBAR */

.sidebar {
    width: 270px;
    min-width: 270px;
    background: #171717;
    border-right: 1px solid #303030;
    display: flex;
    flex-direction: column;
}

.sidebar-top {
    padding: 14px;
}

.brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 17px;
    font-weight: 700;
    margin-bottom: 14px;
}

.logo {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: #10a37f;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
}

.new-chat {
    width: 100%;
    padding: 11px 12px;
    background: #242424;
    border: 1px solid #414141;
    color: #fff;
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
    font-size: 14px;
}

.new-chat:hover {
    background: #303030;
}

.history-title {
    padding: 8px 14px 6px;
    color: #858585;
    font-size: 12px;
    text-transform: uppercase;
}

.chat-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 8px 10px;
}

.empty-history {
    padding: 12px 8px;
    color: #777;
    font-size: 12px;
}

.chat-item {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 2px;
    border-radius: 8px;
}

.chat-open {
    flex: 1;
    min-width: 0;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: #ddd;
    cursor: pointer;
    text-align: left;
    padding: 10px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 13px;
}

.chat-open:hover {
    background: #292929;
}

.chat-item.active .chat-open {
    background: #2f2f2f;
    color: #fff;
}

.chat-delete {
    width: 32px;
    height: 32px;
    border: 0;
    border-radius: 7px;
    background: transparent;
    color: #888;
    cursor: pointer;
    opacity: 0;
}

.chat-item:hover .chat-delete,
.chat-item.active .chat-delete {
    opacity: 1;
}

.chat-delete:hover {
    background: #3a2a2a;
    color: #ff8b8b;
}

.sidebar-bottom {
    padding: 12px 14px;
    border-top: 1px solid #303030;
    color: #888;
    font-size: 12px;
    line-height: 1.8;
}

/* MAIN */

.main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
}

.topbar {
    height: 60px;
    flex-shrink: 0;
    border-bottom: 1px solid #303030;
    padding: 0 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.title {
    font-size: 15px;
    font-weight: 700;
}

.online {
    color: #10a37f;
    font-size: 12px;
}

.chat {
    flex: 1;
    overflow-y: auto;
}

.chat-inner {
    width: min(880px, 100%);
    margin: 0 auto;
    padding: 28px 20px 180px;
}

/* WELCOME */

.welcome {
    min-height: 65vh;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    text-align: center;
}

.welcome-logo {
    width: 66px;
    height: 66px;
    border-radius: 18px;
    background: #10a37f;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 30px;
    margin-bottom: 15px;
}

.welcome h1 {
    margin: 0 0 10px;
    font-size: 30px;
}

.welcome p {
    max-width: 520px;
    margin: 0;
    color: #999;
    line-height: 1.5;
}

.prompt-grid {
    width: min(700px, 100%);
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 20px;
}

.prompt-button {
    border: 1px solid #3b3b3b;
    border-radius: 10px;
    background: #2a2a2a;
    color: #ddd;
    padding: 13px;
    cursor: pointer;
    text-align: left;
    font-size: 13px;
}

.prompt-button:hover {
    background: #333;
}

/* MESSAGES */

.message {
    display: flex;
    gap: 13px;
    margin-bottom: 28px;
}

.avatar {
    width: 31px;
    min-width: 31px;
    height: 31px;
    border-radius: 9px;
    background: #444;
    display: flex;
    align-items: center;
    justify-content: center;
}

.message.assistant .avatar {
    background: #10a37f;
}

.name {
    margin-bottom: 5px;
    font-size: 13px;
    font-weight: 700;
}

.message.assistant .name {
    color: #10a37f;
}

.content {
    line-height: 1.7;
    overflow-wrap: anywhere;
}

pre {
    margin: 10px 0;
    padding: 14px;
    overflow-x: auto;
    border: 1px solid #333;
    border-radius: 9px;
    background: #101010;
}

code {
    font-family: Consolas, "Courier New", monospace;
}

.copy-button {
    padding: 6px 9px;
    border: 1px solid #444;
    border-radius: 6px;
    background: #2a2a2a;
    color: #ddd;
    cursor: pointer;
    font-size: 12px;
}

/* COMPOSER */

.composer-wrap {
    position: fixed;
    left: 270px;
    right: 0;
    bottom: 0;
    padding: 14px 20px 20px;
    background: linear-gradient(
        to top,
        #212121 72%,
        rgba(33,33,33,0)
    );
}

.composer {
    width: min(840px, 100%);
    margin: auto;
    padding: 8px;
    border: 1px solid #444;
    border-radius: 18px;
    background: #2f2f2f;
    display: flex;
    align-items: flex-end;
}

textarea {
    flex: 1;
    max-height: 180px;
    padding: 9px;
    resize: none;
    outline: none;
    border: 0;
    background: transparent;
    color: #fff;
    font-size: 15px;
    line-height: 1.45;
}

textarea::placeholder {
    color: #888;
}

.send-button {
    width: 40px;
    height: 40px;
    flex-shrink: 0;
    border: 0;
    border-radius: 10px;
    background: #10a37f;
    color: #fff;
    cursor: pointer;
    font-size: 19px;
}

.send-button:disabled,
.new-chat:disabled {
    opacity: .4;
    cursor: default;
}

/* MOBILE */

@media (max-width: 700px) {

    .sidebar {
        display: none;
    }

    .composer-wrap {
        left: 0;
        padding: 10px;
    }

    .chat-inner {
        padding-left: 13px;
        padding-right: 13px;
    }

    .welcome h1 {
        font-size: 25px;
    }

    .prompt-grid {
        grid-template-columns: 1fr;
    }
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

<button
    id="newChatButton"
    class="new-chat"
    type="button"
>
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
<div>🧮 Math Expert</div>
<div>💻 Coding Expert</div>
<div>🧠 Smart Context</div>
<div>💾 Memory</div>
<div>🎯 Quiz Mode</div>
<div>📚 Tutor Mode</div>
<div>👻 Created by Matia</div>

</div>

</aside>

<main class="main">

<header class="topbar">

<div class="title">
👻 Ghost-AI
</div>

<div class="online">
● Online
</div>

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

const STORAGE_KEY = "ghost_ai_chats_v7";

let chats = [];
let activeChatId = null;
let streaming = false;

const input =
    document.getElementById("messageInput");

const sendButton =
    document.getElementById("sendButton");

const newChatButton =
    document.getElementById("newChatButton");

const chatList =
    document.getElementById("chatList");

const chat =
    document.getElementById("chat");

const chatInner =
    document.getElementById("chatInner");


function loadChats() {

    try {

        const saved =
            localStorage.getItem(
                STORAGE_KEY
            );

        chats =
            saved
                ? JSON.parse(saved)
                : [];

        if (!Array.isArray(chats)) {
            chats = [];
        }

    } catch (error) {

        chats = [];
    }
}


function saveChats() {

    try {

        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(chats)
        );

    } catch (error) {}
}


function createId() {

    return (
        Date.now().toString(36) +
        Math.random()
            .toString(36)
            .slice(2, 9)
    );
}


function makeTitle(text) {

    const clean =
        String(text)
            .replace(/\s+/g, " ")
            .trim();

    if (!clean) {
        return "New chat";
    }

    if (clean.length <= 38) {
        return clean;
    }

    return (
        clean.slice(0, 38).trim() +
        "..."
    );
}


function escapeHtml(text) {

    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function scrollBottom() {

    requestAnimationFrame(() => {
        chat.scrollTop =
            chat.scrollHeight;
    });
}


function getActiveChat() {

    return chats.find(
        item => item.id === activeChatId
    ) || null;
}


function formatAnswer(text) {

    const parts =
        String(text).split("```");

    let html = "";

    parts.forEach(
        (part, index) => {

            if (index % 2 === 1) {

                let lines =
                    part.split("\n");

                if (
                    lines.length > 0 &&
                    /^[a-zA-Z0-9+#._-]+$/.test(
                        lines[0].trim()
                    )
                ) {
                    lines.shift();
                }

                const code =
                    lines.join("\n");

                html +=
                    "<pre><code>" +
                    escapeHtml(code) +
                    "</code></pre>" +
                    '<button class="copy-button" type="button">' +
                    "Copy code" +
                    "</button>";

            } else {

                html +=
                    escapeHtml(part)
                        .replace(
                            /\n/g,
                            "<br>"
                        );
            }
        }
    );

    return html;
}


function renderChatList() {

    chatList.innerHTML = "";

    if (chats.length === 0) {

        const empty =
            document.createElement("div");

        empty.className =
            "empty-history";

        empty.textContent =
            "No chats yet.";

        chatList.appendChild(empty);

        return;
    }

    const ordered =
        [...chats].sort(
            (a, b) =>
                (b.updatedAt || 0) -
                (a.updatedAt || 0)
        );

    ordered.forEach(chatData => {

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

        open.addEventListener(
            "click",
            () => {

                if (streaming) {
                    return;
                }

                activeChatId =
                    chatData.id;

                renderChatList();
                renderActiveChat();

                input.focus();
            }
        );

        const remove =
            document.createElement("button");

        remove.type = "button";
        remove.className =
            "chat-delete";

        remove.textContent = "🗑";

        remove.addEventListener(
            "click",
            event => {

                event.stopPropagation();

                deleteChat(
                    chatData.id
                );
            }
        );

        item.appendChild(open);
        item.appendChild(remove);

        chatList.appendChild(item);
    });
}


function newChat() {

    if (streaming) {
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


function deleteChat(id) {

    if (streaming) {
        return;
    }

    chats =
        chats.filter(
            item => item.id !== id
        );

    if (activeChatId === id) {

        activeChatId =
            chats.length > 0
                ? chats[0].id
                : null;
    }

    saveChats();

    renderChatList();
    renderActiveChat();
}


function renderWelcome() {

    chatInner.innerHTML = `

        <div class="welcome">

            <div class="welcome-logo">
                👻
            </div>

            <h1>
                How can I help?
            </h1>

            <p>
                Chat, math, coding, learning,
                quizzes and creativity.
            </p>

            <div class="prompt-grid">

                <button
                    class="prompt-button"
                    type="button"
                    data-prompt="Më krijo një histori horror shumë interesante me një twist në fund."
                >
                    👻 Horror Story
                </button>

                <button
                    class="prompt-button"
                    type="button"
                    data-prompt="Zgjidh 3x + 7 = 25 dhe ma shpjego hap pas hapi."
                >
                    🧮 Math Expert
                </button>

                <button
                    class="prompt-button"
                    type="button"
                    data-prompt="Më krijo një mini game të plotë në JavaScript me coins, enemies, score dhe game over."
                >
                    💻 Coding Expert
                </button>

                <button
                    class="prompt-button"
                    type="button"
                    data-prompt="Më bëj një quiz me 10 pyetje për futbollin. Mbaj score."
                >
                    🎯 Quiz
                </button>

                <button
                    class="prompt-button"
                    type="button"
                    data-prompt="Ma shpjego një temë të vështirë sikur jam fillestar."
                >
                    📚 Tutor
                </button>

                <button
                    class="prompt-button"
                    type="button"
                    data-prompt="Çfarë është një black hole? Ma shpjego thjesht por në mënyrë interesante."
                >
                    🌌 Learn
                </button>

            </div>

        </div>
    `;
}


function renderActiveChat() {

    chatInner.innerHTML = "";

    const active =
        getActiveChat();

    if (
        !active ||
        !Array.isArray(active.messages) ||
        active.messages.length === 0
    ) {

        renderWelcome();

        return;
    }

    active.messages.forEach(
        message => {

            addMessageToUI(
                message.role,
                message.content
            );
        }
    );

    scrollBottom();
}


function wireCopyButtons(container) {

    container
        .querySelectorAll(
            ".copy-button"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                async () => {

                    const pre =
                        button
                            .previousElementSibling;

                    if (!pre) {
                        return;
                    }

                    try {

                        await navigator
                            .clipboard
                            .writeText(
                                pre.innerText
                            );

                        button.textContent =
                            "Copied!";

                        setTimeout(
                            () => {
                                button.textContent =
                                    "Copy code";
                            },
                            1000
                        );

                    } catch (error) {

                        button.textContent =
                            "Copy failed";
                    }
                }
            );
        });
}


function addMessageToUI(
    role,
    text
) {

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
                            .replace(
                                /\n/g,
                                "<br>"
                            )
                }
            </div>

        </div>
    `;

    chatInner.appendChild(message);

    wireCopyButtons(message);
}


function createStreamingMessage() {

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


async function sendMessage(
    customText = null
) {

    if (streaming) {
        return;
    }

    let active =
        getActiveChat();

    if (!active) {

        newChat();

        active =
            getActiveChat();
    }

    const text = (
        customText !== null
            ? String(customText)
            : input.value
    ).trim();

    if (!text) {
        return;
    }

    streaming = true;

    sendButton.disabled = true;
    newChatButton.disabled = true;

    input.value = "";
    input.style.height = "auto";

    if (active.messages.length === 0) {
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
            -10
        );

    try {

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
                            messages: recent
                        })
                }
            );

        if (!response.ok) {

            let errorMessage =
                "Server error.";

            try {

                const data =
                    await response.json();

                errorMessage =
                    data.error ||
                    errorMessage;

            } catch (error) {}

            throw new Error(
                errorMessage
            );
        }

        if (!response.body) {

            throw new Error(
                "Streaming is not supported."
            );
        }

        const reader =
            response.body.getReader();

        const decoder =
            new TextDecoder();

        let buffer = "";

        while (true) {

            const result =
                await reader.read();

            if (result.done) {
                break;
            }

            buffer +=
                decoder.decode(
                    result.value,
                    {
                        stream: true
                    }
                );

            const packets =
                buffer.split("\n\n");

            buffer =
                packets.pop() || "";

            for (
                const packet of packets
            ) {

                const line =
                    packet
                        .split("\n")
                        .find(
                            value =>
                                value.startsWith(
                                    "data: "
                                )
                        );

                if (!line) {
                    continue;
                }

                const payload =
                    line.slice(6);

                if (
                    payload === "[DONE]"
                ) {
                    continue;
                }

                let parsed;

                try {

                    parsed =
                        JSON.parse(
                            payload
                        );

                } catch (error) {

                    continue;
                }

                if (
                    parsed.type ===
                    "delta"
                ) {

                    fullAnswer +=
                        parsed.content || "";

                    streamUI.content
                        .textContent =
                            fullAnswer;

                    scrollBottom();
                }

                if (
                    parsed.type ===
                    "error"
                ) {

                    throw new Error(
                        parsed.message ||
                        "AI error."
                    );
                }
            }
        }

        if (!fullAnswer) {

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

    } catch (error) {

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

    } finally {

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

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            sendMessage();
        }
    }
);


input.addEventListener(
    "input",
    function () {

        this.style.height =
            "auto";

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

        if (!button) {
            return;
        }

        const prompt =
            button.getAttribute(
                "data-prompt"
            );

        if (prompt) {
            sendMessage(prompt);
        }
    }
);


loadChats();

if (chats.length > 0) {

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


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "app": "Ghost-AI",
            "model": MODEL
        }
    )


# ============================================================
# NORMAL CHAT API
# ============================================================

@app.route(
    "/api/chat",
    methods=["POST"]
)
def chat_api():

    try:

        data = request.get_json(
            silent=True
        )

        if not isinstance(data, dict):

            return jsonify(
                {
                    "error":
                        "Invalid request."
                }
            ), 400

        incoming =
            data.get(
                "messages",
                []
            )

        messages =
            build_messages(
                incoming
            )

        response =
            client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.5,
                top_p=0.9,
                max_completion_tokens=MAX_OUTPUT_TOKENS
            )

        answer =
            response.choices[0].message.content

        if not answer:
            answer = "Nuk mora përgjigje."

        return jsonify(
            {
                "answer": answer
            }
        )

    except Exception as error:

        return jsonify(
            {
                "error": str(error)
            }
        ), 500


# ============================================================
# STREAMING CHAT
# ============================================================

@app.route(
    "/api/chat/stream",
    methods=["POST"]
)
def chat_stream():

    try:

        data = request.get_json(
            silent=True
        )

        if not isinstance(data, dict):

            return jsonify(
                {
                    "error":
                        "Invalid request."
                }
            ), 400

        incoming =
            data.get(
                "messages",
                []
            )

        messages =
            build_messages(
                incoming
            )

        if messages[-1]["role"] != "user":

            return jsonify(
                {
                    "error":
                        "Last message must be from user."
                }
            ), 400

    except Exception as error:

        return jsonify(
            {
                "error": str(error)
            }
        ), 400

    @stream_with_context
    def generate():

        try:

            stream =
                client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    temperature=0.5,
                    top_p=0.9,
                    max_completion_tokens=MAX_OUTPUT_TOKENS,
                    stream=True
                )

            for chunk in stream:

                if not chunk.choices:
                    continue

                delta =
                    chunk.choices[0].delta.content

                if delta:

                    payload =
                        json.dumps(
                            {
                                "type": "delta",
                                "content": delta
                            },
                            ensure_ascii=False
                        )

                    yield (
                        "data: "
                        + payload
                        + "\n\n"
                    )

            yield "data: [DONE]\n\n"

        except Exception as error:

            payload =
                json.dumps(
                    {
                        "type": "error",
                        "message": str(error)
                    },
                    ensure_ascii=False
                )

            yield (
                "data: "
                + payload
                + "\n\n"
            )

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


# ============================================================
# MEMORY
# ============================================================

@app.route(
    "/api/memory",
    methods=["GET"]
)
def get_memory():

    return jsonify(
        {
            "memory": memory
        }
    )


@app.route(
    "/api/memory",
    methods=["POST"]
)
def add_memory():

    global memory

    try:

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

            return jsonify(
                {
                    "error":
                        "Memory is empty."
                }
            ), 400

        if len(text) > 1000:
            text = text[:1000]

        memory.append(text)

        memory =
            memory[-MAX_MEMORY_ITEMS:]

        save_memory(memory)

        return jsonify(
            {
                "ok": True,
                "memory": memory
            }
        )

    except Exception as error:

        return jsonify(
            {
                "error": str(error)
            }
        ), 500


@app.route(
    "/api/memory",
    methods=["DELETE"]
)
def clear_memory():

    global memory

    memory = []

    save_memory(memory)

    return jsonify(
        {
            "ok": True,
            "memory": []
        }
    )


# ============================================================
# RENDER START
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    print(
        "======================================"
    )

    print(
        "          GHOST-AI ONLINE"
    )

    print(
        "======================================"
    )

    print(
        "MODEL:",
        MODEL
    )

    print(
        "PORT:",
        port
    )

    print(
        "======================================"
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
