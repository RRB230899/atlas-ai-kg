import CytoscapeComponent from "react-cytoscapejs";
import cytoscape from "cytoscape";
import { useState } from "react";

export default function GraphView({ elements }) {
  const [selectedNode, setSelectedNode] = useState(null);

  // Handle node clicks to show details
  const handleCyInit = (cy) => {
    // Click handler for showing node details
    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const data = node.data();
      setSelectedNode(data);
    });

    // Double-click documents to open source URL
    cy.on('dbltap', 'node[type="doc"]', (evt) => {
      const sourceUrl = evt.target.data('sourceUrl');
      if (sourceUrl) {
        window.open(sourceUrl, '_blank');
      }
    });

    // Double-click chunks to show full preview
    cy.on('dbltap', 'node[type="chunk"]', (evt) => {
      const data = evt.target.data();
      // alert(`Chunk ${data.ord}:\n\n${data.preview || data.label}`);
    });
  };

  return (
    <div className="w-full h-full bg-[#0b0f1a] p-2 relative">
      <CytoscapeComponent
        elements={elements}
        style={{ width: "100%", height: "100%", paddingBottom: "40px", paddingLeft: "20px" }}
        cy={handleCyInit}
        layout={{
          name: "cose",
          idealEdgeLength: 120,
          nodeOverlap: 20,
          nodeRepulsion: 10000,
          gravity: 1,
          animate: true,
          animationDuration: 1000,
          componentSpacing: 100,
          coolingFactor: 0.95,
          padding: 30
        }}
        stylesheet={[
          // DOCUMENT NODES (Papers/PDFs)
          {
            selector: 'node[type="doc"]',
            style: {
              shape: "ellipse",
              width: 60,
              height: 60,
              "background-color": "#3B82F6",  // Blue for documents
              "border-color": "#2563EB",
              "border-width": 3,
              label: "data(label)",
              color: "#ffffff",
              "font-size": 13,
              "font-weight": "bold",
              "text-valign": "center",
              "text-halign": "center",
              "text-wrap": "wrap",
              "text-max-width": 100,
              "text-outline-width": 0,
              "shadow-blur": 15,
              "shadow-color": "#3B82F6",
              "shadow-opacity": 0.6,
              "shadow-offset-x": 0,
              "shadow-offset-y": 0
            }
          },

          // CHUNK NODES (Text snippets)
          {
            selector: 'node[type="chunk"]',
            style: {
              shape: "roundrectangle",  // Different shape for chunks
              width: 35,
              height: 35,
              "background-color": "#6B7280",  // Gray for chunks
              "border-color": "#4B5563",
              "border-width": 2,
              label: "data(label)",
              color: "#F3F4F6",
              "font-size": 9,
              "text-valign": "top",
              "text-halign": "center",
              "text-wrap": "wrap",
              "text-max-width": 120,
              "text-outline-width": 4,
              "text-outline-color": "#1F2937",
              "shadow-blur": 8,
              "shadow-color": "#6B7280",
              "shadow-opacity": 0.4,
              "shadow-offset-x": 0,
              "shadow-offset-y": 0
            }
          },

          // ENTITY NODES (Color-coded by type)
          {
            selector: 'node[type="entity"]',
            style: {
              shape: "ellipse",
              width: 45,
              height: 45,
              "background-color": "#8B5CF6",  // Default purple
              "border-color": "#7C3AED",
              "border-width": 2,
              label: "data(label)",
              color: "#ffffff",
              "font-size": 11,
              "text-valign": "center",
              "text-halign": "center",
              "text-wrap": "wrap",
              "text-max-width": 110,
              "text-outline-width": 5,
              "text-outline-color": "#1F2937",
              "shadow-blur": 12,
              "shadow-color": "#8B5CF6",
              "shadow-opacity": 0.5,
              "shadow-offset-x": 0,
              "shadow-offset-y": 0
            }
          },

          // Entity type-specific colors
          {
            selector: 'node[entityType="PERSON"]',
            style: {
              "background-color": "#10B981",  // Green
              "border-color": "#059669",
              "shadow-color": "#10B981"
            }
          },
          {
            selector: 'node[entityType="ORGANIZATION"]',
            style: {
              "background-color": "#F59E0B",  // Orange
              "border-color": "#D97706",
              "shadow-color": "#F59E0B"
            }
          },
          {
            selector: 'node[entityType="TECHNOLOGY"]',
            style: {
              "background-color": "#8B5CF6",  // Purple
              "border-color": "#7C3AED",
              "shadow-color": "#8B5CF6"
            }
          },
          {
            selector: 'node[entityType="LOCATION"]',
            style: {
              "background-color": "#EF4444",  // Red
              "border-color": "#DC2626",
              "shadow-color": "#EF4444"
            }
          },
          {
            selector: 'node[entityType="CONCEPT"]',
            style: {
              "background-color": "#EAB308",  // Yellow
              "border-color": "#CA8A04",
              "shadow-color": "#EAB308"
            }
          },

          // HOVER & SELECTED STATES
          {
            selector: "node:hover",
            style: {
              "border-width": 4,
              "border-color": "#fff",
              "shadow-blur": 20,
              "shadow-opacity": 0.8
            }
          },
          {
            selector: "node:selected",
            style: {
              "background-blacken": -0.2,
              "border-width": 5,
              "border-color": "#FBBF24",  // Gold selection
              "shadow-blur": 25,
              "shadow-opacity": 0.9
            }
          },

          // EDGES (Relationships)
          {
            selector: "edge",
            style: {
              width: 2,
              "line-color": "#4B5563",
              "curve-style": "bezier",
              "target-arrow-shape": "triangle",
              "target-arrow-color": "#4B5563",
              "arrow-scale": 1.2,
              label: "data(label)",
              "font-size": 9,
              color: "#9CA3AF",
              "text-background-color": "#0b0f1a",
              "text-background-opacity": 0.8,
              "text-background-padding": 3,
              "text-rotation": "autorotate"
            }
          },
          {
            selector: "edge:hover",
            style: {
              "line-color": "#D1D5DB",
              "target-arrow-color": "#D1D5DB",
              width: 3,
              color: "#F3F4F6"
            }
          },
          {
            selector: "edge:selected",
            style: {
              "line-color": "#FBBF24",
              "target-arrow-color": "#FBBF24",
              width: 4
            }
          }
        ]}
      />

      {/* Node Details Sidebar */}
      {selectedNode && (
        <div className="absolute top-4 right-4 bg-gray-900 border border-gray-700 rounded-lg p-4 max-w-xs shadow-xl">
          <div className="flex justify-between items-start mb-2">
            <h3 className="text-white font-bold text-sm">
              {selectedNode.type === "doc" && "📄 Document"}
              {selectedNode.type === "chunk" && "📝 Chunk"}
              {selectedNode.type === "entity" && `🏷️ Entity (${selectedNode.entityType || "Unknown"})`}
            </h3>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-gray-400 hover:text-white"
            >
              ✕
            </button>
          </div>

          {/* Document Details */}
          {selectedNode.type === "doc" && (
            <div className="text-sm space-y-2">
              <p className="text-gray-300">
                <strong>Title:</strong> {selectedNode.fullTitle || selectedNode.label}
              </p>
              {selectedNode.sourceUrl && (
                <a
                  href={selectedNode.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 block"
                >
                  🔗 Open Source PDF
                </a>
              )}
            </div>
          )}

          {/* Chunk Details */}
          {selectedNode.type === "chunk" && (
            <div className="text-sm space-y-2">
              <p className="text-gray-400 text-xs">Chunk #{selectedNode.ord}</p>
              <p className="text-gray-300 text-xs leading-relaxed">
                {selectedNode.preview || selectedNode.label}
              </p>
            </div>
          )}

          {/* Entity Details */}
          {selectedNode.type === "entity" && (
            <div className="text-sm space-y-2">
              <p className="text-gray-300">
                <strong>Name:</strong> {selectedNode.name || selectedNode.label}
              </p>
              <p className="text-gray-300">
                <strong>Type:</strong>{" "}
                <span className="px-2 py-1 bg-purple-900 text-purple-200 rounded text-xs">
                  {selectedNode.entityType || "Unknown"}
                </span>
              </p>
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-gray-900/95 backdrop-blur-sm border border-gray-700 rounded-lg p-3 text-xs max-w-[180px]">
        <div className="text-white font-bold mb-2">Legend</div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#3B82F6]"></div>
            <span className="text-gray-300">Document</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-[#6B7280]"></div>
            <span className="text-gray-300">Chunk</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#10B981]"></div>
            <span className="text-gray-300">Person</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#F59E0B]"></div>
            <span className="text-gray-300">Organization</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#8B5CF6]"></div>
            <span className="text-gray-300">Technology</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#EF4444]"></div>
            <span className="text-gray-300">Location</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-[#EAB308]"></div>
            <span className="text-gray-300">Concept</span>
          </div>
        </div>
        <div className="mt-3 pt-2 border-t border-gray-700 text-gray-400">
          <div>💡 Double-click documents to open PDF</div>
          <div>💡 Double-click chunks to see preview</div>
        </div>
      </div>
    </div>
  );
}