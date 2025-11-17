"use client";
import { useState } from "react";
import axios from "axios";

export default function IngestPage() {
    const [file, setFile] = useState<File | null>(null);
    const [text, setText] = useState("");
    const [url, setUrl] = useState("");
    const [title, setTitle] = useState("");

    const submitDocument = async () => {
        const form = new FormData();
        form.append("title", title);

        if (file) form.append("file", file);
        if (text) form.append("text", text);
        if (url) form.append("url", url);

        const res = await axios.post("http://localhost:8001/documents", form);
        alert("Document ingested: " + res.data.docId);
    };

    return (
        <div className="p-8 max-w-xl mx-auto space-y-4">
            <h1 className="text-3xl font-bold">Add Knowledge</h1>

            <input
                className="border p-2 w-full"
                placeholder="Document Title"
                value={title}
                onChange={e => setTitle(e.target.value)}
            />

            <input
                type="file"
                onChange={e => {
                    const files = e.target.files;
                    setFile(files && files.length > 0 ? files[0] : null);
                }}
            />

            <input
                className="border p-2 w-full"
                placeholder="Website URL"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
            />

            <textarea
                className="border p-2 w-full"
                placeholder="Paste text here"
                value={text}
                onChange={(e) => setText(e.target.value)}
            />

            <button
                onClick={submitDocument}
                className="bg-black text-white px-4 py-2 rounded"
            >
                Submit to RAG
            </button>
        </div>
    );
}
