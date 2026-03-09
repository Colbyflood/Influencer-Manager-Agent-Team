import { useState } from "react";
import { CampaignList } from "./components/CampaignList";
import { CampaignDetail } from "./components/CampaignDetail";

function App() {
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Campaign Dashboard
          </h1>
        </div>
      </header>

      {/* Main content */}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {selectedCampaignId ? (
          <CampaignDetail
            campaignId={selectedCampaignId}
            onBack={() => setSelectedCampaignId(null)}
          />
        ) : (
          <CampaignList onSelect={setSelectedCampaignId} />
        )}
      </main>
    </div>
  );
}

export default App;
