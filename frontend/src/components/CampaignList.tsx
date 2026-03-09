import { usePolling } from "../hooks/usePolling";
import type { CampaignListResponse } from "../types/campaign";
import { CampaignCard } from "./CampaignCard";

interface CampaignListProps {
  onSelect?: (campaignId: string) => void;
}

export function CampaignList({ onSelect }: CampaignListProps = {}) {
  const { data, loading, error } = usePolling<CampaignListResponse>(
    "/api/v1/campaigns",
    30000
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <p className="font-semibold text-red-800">Error loading campaigns</p>
        <p className="mt-1 text-sm text-red-600">{error}</p>
        <p className="mt-2 text-xs text-red-400">Data may be stale</p>
      </div>
    );
  }

  if (!data || data.campaigns.length === 0) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="rounded-lg border border-gray-200 bg-white px-8 py-6 text-center shadow-sm">
          <p className="text-gray-500">No campaigns yet</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header with count and refresh indicator */}
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-gray-600">
          {data.total} campaign{data.total !== 1 ? "s" : ""}
        </p>
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-green-400" />
          <span className="text-xs text-gray-400">
            Auto-refreshing every 30s
          </span>
        </div>
      </div>

      {/* Error banner (non-blocking, data still available) */}
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3">
          <p className="text-sm text-red-600">
            Refresh failed: {error}. Showing cached data.
          </p>
        </div>
      )}

      {/* Campaign grid */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
        {data.campaigns.map((campaign) => (
          <CampaignCard key={campaign.campaign_id} campaign={campaign} onSelect={onSelect} />
        ))}
      </div>
    </div>
  );
}
