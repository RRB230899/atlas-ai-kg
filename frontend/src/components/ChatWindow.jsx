import { useState, useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import GraphView from "./GraphView";
import { searchRAGWithGraph } from "../api/atlasAPI";

export default function ChatWindow({ messages, graphData, onUpdateMessages, onUpdateGraph }) {
  const [localMessages, setLocalMessages] = useState(messages);
  const [query, setQuery] = useState("");
  const [showGraph, setShowGraph] = useState(true);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  // Update local messages when messages prop changes
  useEffect(() => { 
    setLocalMessages(messages);
  }, [messages]);
  
  // Auto-scroll to bottom when messages change
  useEffect(() => { 
    bottomRef.current?.scrollIntoView({ behavior: "smooth" }); 
  }, [localMessages]);

  const handleSend = async () => {
    if (!query.trim()) return;

    const userMsg = { role: "user", text: query };
    let newMessages = [...localMessages, userMsg];
    setLocalMessages(newMessages);
    setLoading(true);

    try {
      console.log("[ChatWindow] sending:", query);
      
      // Pass showGraph value to determine if graph should be included
      const data = await searchRAGWithGraph(query, 5, showGraph);
      console.log("[ChatWindow] received:", data);
      
      // Build a simple text answer from top hits
      const text =
        data.hits?.length
          ? data.hits.map((h, i) => {
              const preview = h.text?.slice(0, 280) || "";
              const ref = h.sha256 ? `[${h.sha256.slice(0, 8)}:${h.ord}]` : "";
              const title = h.title ? `\n📄 ${h.title}` : "";
              return `${i+1}. ${preview} ${ref}${title}`;
            }).join("\n\n")
          : "No results found.";

      const botMsg = { role: "bot", text };
      newMessages = [...newMessages, botMsg];
      setLocalMessages(newMessages);
      onUpdateMessages(newMessages);

      // Store graph data in parent component via callback
      if (data.graph && (data.graph.nodes?.length || data.graph.edges?.length)) {
        console.log("[ChatWindow] Graph data received:", {
          nodes: data.graph.nodes?.length || 0,
          edges: data.graph.edges?.length || 0
        });
        
        // Cytoscape expects a flat array of elements
        const graphElements = [
          ...(data.graph.nodes || []), 
          ...(data.graph.edges || [])
        ];
        
        // Save to parent (persists in chat history)
        onUpdateGraph(graphElements);
      } else {
        console.log("[ChatWindow] No graph data in response");
        onUpdateGraph(null);
      }
    } catch (err) {
      console.error("[ChatWindow] Error:", err);
      const botMsg = { 
        role: "bot", 
        text: `Error: ${err.message || 'Failed to fetch results. Please check your connection and try again.'}` 
      };
      newMessages = [...newMessages, botMsg];
      setLocalMessages(newMessages);
      onUpdateMessages(newMessages);
      
      // Clear graph on error
      onUpdateGraph(null);
    } finally {
      setLoading(false);
    }

    setQuery("");
  };

  // Clear graph via parent callback
  const handleClearGraph = () => {
    onUpdateGraph(null);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-gray-100 flex-1">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-950">
        <div className="text-sm font-semibold text-gray-300">ATLAS — RAG + Knowledge Graph</div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-300 cursor-pointer">
            <input 
              type="checkbox" 
              checked={showGraph} 
              onChange={() => setShowGraph(v => !v)}
              className="rounded"
            />
            Show graph
          </label>
          
          {/* Clear graph button */}
          {graphData && (
            <button
              onClick={handleClearGraph}
              className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded hover:bg-gray-800"
              title="Clear graph"
            >
              Clear graph
            </button>
          )}
        </div>
      </div>

      {/* Messages & Graph Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {localMessages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center space-y-2">
              <div className="text-4xl">💬</div>
              <div className="text-lg font-semibold">Start a conversation</div>
              <div className="text-sm">Ask Atlas about your documents</div>
            </div>
          </div>
        )}
        
        {localMessages.map((msg, i) => (
          <MessageBubble key={i} {...msg} />
        ))}
        
        {/* Graph Visualization - Uses graphData prop from parent */}
        {showGraph && graphData && graphData.length > 0 && (
          <div className="mt-4 rounded-lg overflow-hidden bg-[#0b0f1a] border border-gray-800 shadow-lg">
            <div className="bg-gray-800 px-3 py-2 text-xs font-semibold text-gray-300 border-b border-gray-700 flex items-center justify-between">
              <span>📊 Knowledge Graph ({graphData.filter(e => e.data?.type !== undefined).length} nodes)</span>
              <button
                onClick={handleClearGraph}
                className="text-gray-500 hover:text-gray-300 text-xs"
                title="Clear graph"
              >
                ✕
              </button>
            </div>
            <div className="h-96">
              <GraphView elements={graphData} />
            </div>
          </div>
        )}

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
            <span>Searching...</span>
          </div>
        )}
        
        <div ref={bottomRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-gray-800 bg-gray-950">
        <div className="flex gap-3">
          <input
            className="flex-1 bg-gray-800 text-white px-4 py-3 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 placeholder-gray-500"
            placeholder="Ask Atlas about your documents..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && handleSend()}
            disabled={loading}
          />
          <button 
            onClick={handleSend} 
            disabled={loading || !query.trim()}
            className="px-6 py-3 bg-indigo-600 rounded-lg hover:bg-indigo-500 disabled:bg-gray-700 disabled:cursor-not-allowed font-semibold transition-colors"
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
