export default function MessageBubble({ role, text }) {
  const isUser = role === "user";
  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} transition-all`}
    >
      <div
        className={`p-3 max-w-xl rounded-lg shadow-md whitespace-pre-wrap ${
          isUser
            ? "bg-indigo-600 text-white"
            : "bg-gray-800 text-gray-100 border border-gray-700"
        }`}
      >
        {text}
      </div>
    </div>
  );
}
