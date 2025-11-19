// Format API results into text
export function formatResults(results) {
  return results
    .map((r) => {
      const entities = r.entities.map((e) => e.name).join(", ");
      return `📄 ${r.text}\nEntities: ${entities}`;
    })
    .join("\n\n");
}

// Create a title for the chat history
export function makeChatTitle(messages) {
  const firstMsg = messages[0]?.text || "New Chat";
  return firstMsg.slice(0, 30);
}
