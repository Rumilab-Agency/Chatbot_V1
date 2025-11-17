import express from "express";
import bodyParser from "body-parser";
import fetch from "node-fetch";
import dotenv from "dotenv";
import cors from "cors";   // <-- ADD THIS

dotenv.config();

const app = express();

app.use(cors({
    origin: ["http://localhost:3000", "http://127.0.0.1:3000"],   // Next.js dev URL
    methods: ["GET", "POST"],
    allowedHeaders: ["Content-Type"],
}));

app.use(bodyParser.json());

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL || "http://rag_service:8001";
const PORT = process.env.PORT || 3010;

app.post("/chat", async (req, res) => {
    const userMessage = req.body.message;
    if (!userMessage) return res.status(400).json({ error: "Message required" });

    try {
        // 1️⃣ Get context from RAG
        const response = await fetch(`${RAG_SERVICE_URL}/query?message=${encodeURIComponent(userMessage)}`);
        const ragData = await response.json();

        const contextChunks = ragData.retrieved_chunks || [];

        // 2️⃣ Decide what to do if no context is found
        if (contextChunks.length === 0) {
            return res.json({
                reply: "I’m sorry, I don’t have relevant information about that yet. Please try rephrasing your question or adding more details.",
            });
        }

        // 3️⃣ Create a strict system prompt for LLM
        const contextText = contextChunks.join("\n\n");

        const prompt = `
You are a helpful assistant. Answer **only** using the following context.
If the answer is not contained in the context, respond with:
"I’m sorry, I don’t have relevant information about that."

Context:
${contextText}

User message:
${userMessage}
    `;

        // 4️⃣ Query OpenAI
        const llmResponse = await fetch("https://api.openai.com/v1/chat/completions", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${OPENAI_API_KEY}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: "gpt-4o-mini",
                messages: [{ role: "user", content: prompt }]
            })
        });

        const data = await llmResponse.json();
        const reply = data.choices?.[0]?.message?.content || "I’m sorry, something went wrong.";

        res.json({ reply });

    } catch (error) {
        console.error("❌ Chat error:", error);
        res.status(500).json({ error: "Internal server error" });
    }
});

app.listen(PORT, () => console.log(`💬 Chat service running on port ${PORT}`));
