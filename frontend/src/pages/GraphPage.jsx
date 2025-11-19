import { useState, useEffect } from 'react';
import GraphView from '../components/GraphView';
import { fetchSubgraph } from '../api/atlasAPI';

export default function GraphPage({ entity }) {
  const [elements, setElements] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!entity) return;
    setLoading(true);

    fetchSubgraph(entity)
      .then(data => {
        setElements(data.elements || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [entity]);

  if (!entity) {
    return <div className="text-center text-gray-300 p-10">Select an entity to view its graph.</div>;
  }

  if (loading) {
    return <div className="text-center text-gray-300 p-10">Loading graph…</div>;
  }

  return (
    <div className="h-screen bg-gray-900 p-4">
      <GraphView elements={elements} />
    </div>
  );
}
