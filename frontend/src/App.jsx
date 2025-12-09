import { useState, useEffect } from "react";
import SideBar from "./components/SideBar";
import ChatWindow from "./components/ChatWindow";
import { makeChatTitle } from "./utils/chatLogger";

function App() {
  const [history, setHistory] = useState([
    // Start with one empty chat
    { title: "New Chat", messages: [], graphData: null }
  ]);
  const [activeChat, setActiveChat] = useState(0);

  // Load from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("atlas_history");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.length > 0) {
          setHistory(parsed);
          setActiveChat(0);
        }
      } catch (error) {
        console.error("Failed to load history:", error);
      }
    }
  }, []);

  // Save to localStorage whenever history changes
  useEffect(() => {
    if (history.length > 0) {
      localStorage.setItem("atlas_history", JSON.stringify(history));
    }
  }, [history]);
  
  // New Chat Handler
  const startNewChat = () => {
    const newChat = { 
      title: "New Chat", 
      messages: [],
      graphData: null
    };
    setHistory((prev) => [...prev, newChat]);
    setActiveChat(history.length); // Switch to the new chat
  };

  // Update the active chat's messages
  const updateActiveChat = (messages) => {
    setHistory((prev) => {
      const updated = [...prev];
      updated[activeChat] = {
        ...updated[activeChat],
        title: makeChatTitle(messages),
        messages,
      };
      return updated;
    });
  };

  // Update graph data for active chat
  const handleUpdateGraph = (graphElements) => {
    setHistory((prev) => {
      const updated = [...prev];
      updated[activeChat] = {
        ...updated[activeChat],
        graphData: graphElements
      };
      return updated;
    });
  };

  // Get current chat safely
  const currentChat = history[activeChat] || { 
    title: "New Chat", 
    messages: [], 
    graphData: null 
  };

  return (
    <div className="flex h-screen bg-black">
      <SideBar
        history={history}
        onSelect={setActiveChat}
        onNewChat={startNewChat}
      />

      <ChatWindow
        key={activeChat}
        messages={currentChat.messages}
        graphData={currentChat.graphData}
        onUpdateMessages={updateActiveChat}
        onUpdateGraph={handleUpdateGraph}
      />
    </div>
  );
}

export default App;
