import React from "react";
import CytoscapeComponent from "react-cytoscapejs";
import cytoscape from "cytoscape";
import dagre from "cytoscape-dagre";

cytoscape.use(dagre);

export default function GraphView({ elements }) {
  return (
    <div className="w-full h-full bg-gray-100 p-4">
      <CytoscapeComponent
        elements={elements}
        style={{ width: "100%", height: "100%" }}
        layout={{ name: "dagre" }}
        stylesheet={[
          {
            selector: "node",
            style: {
              "background-color": "#2563eb",
              label: "data(label)",
              color: "white",
              "font-size": 12,
              "text-wrap": "wrap",
              "text-max-width": 100
            },
          },
          {
            selector: "edge",
            style: {
              width: 2,
              "line-color": "#94a3b8",
              "target-arrow-color": "#94a3b8",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
            },
          },
        ]}
      />
    </div>
  );
}
