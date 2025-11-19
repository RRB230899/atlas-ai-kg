export default function SideBar({ history, onSelect, onNewChat }) {
  return (
    <div className="w-64 bg-gray-950 p-4 border-r border-gray-800" style={{color: 'white'}}>

      <button
        onClick={onNewChat}
        className="w-full mb-4 p-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500"
      >
        + New Chat
      </button>

      <h2 className="text-lg font-semibold mb-4 text-white">Chat History</h2>

      <ul className="space-y-2">
        {history.map((h, i) => (
          <li
            key={i}
            onClick={() => onSelect(i)}
            className="cursor-pointer p-2 rounded hover:bg-gray-800"
          >
            {h.title || `Chat ${i + 1}`}
          </li>
        ))}
      </ul>
    </div>
  );
}
