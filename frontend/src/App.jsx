import { useState, useEffect } from "react";
import SideBar from "./components/SideBar";
import ChatWindow from "./components/ChatWindow";
import { makeChatTitle } from "./utils/chatLogger";

function App() {
  const [history, setHistory] = useState([]);
  const [activeChat, setActiveChat] = useState(0);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load from localStorage on mount BEFORE initializing
  useEffect(() => {
    const saved = localStorage.getItem("atlas_history");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.length > 0) {
          console.log("[App] Loaded history from localStorage:", parsed.length, "chats");
          setHistory(parsed);
          setActiveChat(0); // Start with first chat
          setIsLoaded(true);
          return; // Exit early - don't create default chat
        }
      } catch (error) {
        console.error("Failed to load history:", error);
      }
    }
    
    // Only create default chat if nothing in localStorage
    console.log("[App] No saved history, creating default chat");
    setHistory([{ title: "New Chat", messages: [], graphData: null }]);
    setActiveChat(0);
    setIsLoaded(true);
  }, []);

  // Save to localStorage whenever history changes (after initial load)
  useEffect(() => {
    if (!isLoaded) return; // Don't save during initial load
    
    if (history.length > 0) {
      console.log("[App] Saving history to localStorage:", history.length, "chats");
      localStorage.setItem("atlas_history", JSON.stringify(history));
    }
  }, [history, isLoaded]);
  
  // New Chat Handler
  const startNewChat = () => {
    console.log("[App] Creating new chat");
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
    console.log("[App] Updating messages for chat", activeChat);
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
    console.log("[App] Updating graph for chat", activeChat, 
      graphElements ? `${graphElements.length} elements` : 'null');
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

  // Show loading state while checking localStorage
  if (!isLoaded) {
    return (
      <div className="flex items-center justify-center h-screen bg-black text-white">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white mx-auto mb-4"></div>
          <div>Loading...</div>
        </div>
      </div>
    );
  }

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
