import { useState, useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import { searchWithEntities } from "../api/atlasAPI";
import { formatResults } from "../utils/chatLogger";

export default function ChatWindow({ messages, onUpdateMessages }) {
  const [localMessages, setLocalMessages] = useState(messages);
  const [query, setQuery] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    setLocalMessages(messages);
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [localMessages]);

  const handleSend = async () => {
    if (!query.trim()) return;

    const userMsg = { role: "user", text: query };
    let newMessages = [...localMessages, userMsg];
    setLocalMessages(newMessages);

    let botMsg;

    try {
      const data = await searchWithEntities(query, 3);
      botMsg = { role: "bot", text: formatResults(data.results) };
    } catch (err) {
      botMsg = { role: "bot", text: "Error fetching results." };
    }

    newMessages = [...newMessages, botMsg];
    setLocalMessages(newMessages);

    onUpdateMessages(newMessages);
    setQuery("");
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-gray-100 flex-1">
      <div className="flex-1 overflow-y-scroll p-4 space-y-3">
        {localMessages.map((msg, i) => (
          <MessageBubble key={i} {...msg} />
        ))}
        <div ref={bottomRef}>
        </div>
      </div>

      <div className="p-4 border-t border-gray-700 flex">
        <input
          className="flex-1 bg-gray-800 text-white p-3 rounded-lg outline-none"
          placeholder="Ask Atlas..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />

        <button
          onClick={handleSend}
          className="ml-3 px-5 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-500"
        >
          Send
        </button>
      </div>
    </div>
  );
}
