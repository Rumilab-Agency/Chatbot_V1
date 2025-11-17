"use client";
import { useState } from "react";
import axios from "axios";

type Message = {
    role: "user" | "assistant";
    content: string;
};

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);

    const sendMessage = async (msg: string) => {
        setMessages(prev => [...prev, { role: "user", content: msg }]);

        const res = await axios.post("http://localhost:3010/chat", {
            message: msg
        }, { withCredentials: false });

        setMessages(prev => [...prev, { role: "assistant", content: res.data.reply }]);
    };

    return (
        <div className="p-8 max-w-xl mx-auto">
            <h1 className="text-3xl font-bold mb-4">Chat Test</h1>

            <div className="border h-96 p-4 overflow-y-scroll mb-4">
                {messages.map((m, i) => (
                    <div key={i} className={`my-2 ${m.role === "user" ? "text-right" : ""}`}>
                        <span className={`inline-block px-3 py-2 rounded ${m.role === "user" ? "bg-blue-500 text-white" : "bg-gray-200"}`}>
                            {m.content}
                        </span>
                    </div>
                ))}
            </div>

            <ChatInput onSend={sendMessage} />
        </div>
    );
}

type ChatInputProps = {
    onSend: (msg: string) => void;
};

function ChatInput({ onSend }: ChatInputProps) {
    const [text, setText] = useState("");

    return (
        <div className="flex gap-2">
            <input
                className="border flex-1 p-2"
                value={text}
                onChange={e => setText(e.target.value)}
            />
            <button
                className="bg-black text-white px-4 py-2"
                onClick={() => {
                    onSend(text);
                    setText("");
                }}
            >
                Send
            </button>
        </div>
    );
}
