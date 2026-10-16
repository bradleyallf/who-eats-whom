import { useEffect, useState } from 'react';
import { apiClient } from '../../utils';

interface StatsSummary {
  observations: number;
  edges: number;
  taxa: number;
  locations: number;
}

export const InteractiveFoodWeb = () => {
  const src = `${import.meta.env.BASE_URL}predator_prey.html`;

  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [hasError, setHasError] = useState(false);

  // Added this block of code to call the food-web/summary endpoint instead of displaying the summary statistics from the static file - Shriya

  useEffect(() => {
    let mounted = true;

    apiClient
      .get('/v1/food-web/summary')
      .then((res) => {
        if (!mounted) return;
        setStats(res.data);
      })
      .catch(() => {
        if (!mounted) return;
        setHasError(true);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const metrics = [
    {
      label: 'Observations available',
      value: stats?.observations,
    },
    {
      label: '# of Unique Nodes',
      value: stats?.taxa,
    },
    {
      label: '# of Edges',
      value: stats?.edges,
    },
    {
      label: 'Locations',
      value: stats?.locations,
    },
  ];

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {metrics.map(({ label, value }) => (
          <div key={label} className="p-4 bg-white rounded-lg shadow text-center">
            <p className="text-3xl font-bold">
              {value !== undefined && value !== null
                ? value.toLocaleString()
                : '—'}
            </p>
            <p className="text-sm text-gray-600">{label}</p>
          </div>
        ))}
      </div>

      {hasError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          Unable to load the latest network statistics.
        </div>
      )}

      <div className="w-full h-[80vh] border rounded overflow-hidden shadow">
        <iframe
          src={src}
          className="w-full h-full"
          title="Interactive Food Web"
        />
      </div>
    </div>
  );
};
