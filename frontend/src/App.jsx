import { useState, useEffect } from "react";
import SideBar from "./components/SideBar";
import ChatWindow from "./components/ChatWindow";
import { makeChatTitle } from "./utils/chatLogger";

function App() {
  const [history, setHistory] = useState([]);
  const [activeChat, setActiveChat] = useState(null);

  useEffect(() => {
    const saved = localStorage.getItem("atlas_history");
    if (saved) setHistory(JSON.parse(saved));
  }, []);

  useEffect(() => {
    localStorage.setItem("atlas_history", JSON.stringify(history));
  }, [history]);
  
  // New Chat Handler
  const startNewChat = () => {
    const newChat = { title: "New Chat", messages: [] };
    setHistory((prev) => [...prev, newChat]);
    setActiveChat(history.length); // index of new chat
  };

  // Create a chat automatically if none exists
  const ensureChatExists = () => {
    if (activeChat !== null) return activeChat;

    const newChat = { title: "New Chat", messages: [] };
    setHistory((prev) => [...prev, newChat]);

    const newIndex = history.length;
    setActiveChat(newIndex);

    return newIndex;
  };

  // Update the chat's messages
  const updateActiveChat = (messages) => {
    const index = ensureChatExists();

    setHistory((prev) => {
      const updated = [...prev];
      updated[index] = {
        title: makeChatTitle(messages),
        messages,
      };
      return updated;
    });
  };

  return (
    <div className="flex h-screen bg-black">
      <SideBar
        history={history}
        onSelect={setActiveChat}
        onNewChat={startNewChat}
      />

      <ChatWindow
        messages={history[activeChat]?.messages || []}
        onUpdateMessages={updateActiveChat}
      />
    </div>
  );
}

export default App;
