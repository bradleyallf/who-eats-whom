// src/pages/InteractiveFoodWeb.tsx
import React from 'react';

export const InteractiveFoodWeb: React.FC = () => {
  const src = `${import.meta.env.BASE_URL}predator_prey.html`;

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-lg shadow text-center">
          <p className="text-3xl font-bold">10,330</p>
          <p className="text-sm text-gray-600">Observations available</p>
        </div>
        <div className="p-4 bg-white rounded-lg shadow text-center">
          <p className="text-3xl font-bold">1,088</p>
          <p className="text-sm text-gray-600">Species connected</p>
        </div>
        <div className="p-4 bg-white rounded-lg shadow text-center">
          <p className="text-3xl font-bold">1,346</p>
          <p className="text-sm text-gray-600">Taxons connected</p>
        </div>
        <div className="p-4 bg-white rounded-lg shadow text-center">
          <p className="text-3xl font-bold">122</p>
          <p className="text-sm text-gray-600">Locations</p>
        </div>
      </div>

      <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
        <p className="text-red-600 italic">
          The edges are arrows that represent predator prey interactions (predator to prey). The nodes
          are species coming from the WhoEatWhom iNaturalist page. 
        </p>
      </div>

      {/* 4) Full-screen iframe */}
      <div className="w-full h-[80vh] border rounded overflow-hidden">
        <iframe
          src={src}
          className="w-full h-full"
          title="Interactive Food Web"
        />
      </div>
    </div>
  );
};
