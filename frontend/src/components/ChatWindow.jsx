// frontend/src/components/ChatWindow.jsx
import { useState, useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import GraphView from "./GraphView";
import { searchRAGWithGraph } from "../api/atlasAPI";
// import { askOpenAI } from "../api/atlasAPI";  // keep if you still use it
import { formatResults } from "../utils/chatLogger";

export default function ChatWindow({ messages, onUpdateMessages }) {
  const [localMessages, setLocalMessages] = useState(messages);
  const [query, setQuery] = useState("");
  const [graphElements, setGraphElements] = useState(null);
  const [showGraph, setShowGraph] = useState(true);
  const bottomRef = useRef(null);

  useEffect(() => { setLocalMessages(messages); }, [messages]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [localMessages]);

  const handleSend = async () => {
    if (!query.trim()) return;

    const userMsg = { role: "user", text: query };
    let newMessages = [...localMessages, userMsg];
    setLocalMessages(newMessages);

    try {
      console.log("[ChatWindow] sending:", query);
      const data = await searchRAGWithGraph(query, 5, false);
      console.log("[ChatWindow] received:", data);
      // build a simple text answer from top hits
      const text =
        data.hits?.length
          ? data.hits.map((h, i) => `${i+1}. ${h.text?.slice(0, 280) || ""} ${h.sha256 ? `[${h.sha256}:${h.ord}]` : ""}`).join("\n\n")
          : "No results.";

      const botMsg = { role: "bot", text };
      newMessages = [...newMessages, botMsg];
      setLocalMessages(newMessages);
      onUpdateMessages(newMessages);

      // stash Cytoscape elements if present
      if (data.graph && (data.graph.nodes?.length || data.graph.edges?.length)) {
        // Cytoscape expects a flat array of elements
        setGraphElements([...(data.graph.nodes||[]), ...(data.graph.edges||[])]);
      } else {
        setGraphElements(null);
      }
    } catch (err) {
      const botMsg = { role: "bot", text: "Error fetching results." };
      newMessages = [...newMessages, botMsg];
      setLocalMessages(newMessages);
      onUpdateMessages(newMessages);
    }

    setQuery("");
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-gray-100 flex-1">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800">
        <div className="text-sm text-gray-300">ATLAS — RAG + Graph</div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showGraph} onChange={()=>setShowGraph(v=>!v)} />
          Show graph
        </label>
      </div>

      <div className="flex-1 overflow-y-scroll p-4 space-y-3">
        {localMessages.map((msg, i) => <MessageBubble key={i} {...msg} />)}
        {/* graph area */}
        {showGraph && graphElements && (
          <div className="h-96 rounded-lg overflow-hidden bg-white/5 border border-gray-800">
            <GraphView elements={graphElements} />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="p-4 border-t border-gray-800 flex">
        <input
          className="flex-1 bg-gray-800 text-white p-3 rounded-lg outline-none"
          placeholder="Ask Atlas..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <button onClick={handleSend} className="ml-3 px-5 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-500">
          Send
        </button>
      </div>
    </div>
  );
}
