import type { CampaignSummary } from "../types/campaign";

interface CampaignCardProps {
  campaign: CampaignSummary;
  onSelect?: (campaignId: string) => void;
}

export function CampaignCard({ campaign, onSelect }: CampaignCardProps) {
  const { status_counts, metrics } = campaign;

  return (
    <div
      onClick={() => onSelect?.(campaign.campaign_id)}
      className="cursor-pointer rounded-lg border border-gray-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            {campaign.client_name}
          </h3>
          <p className="text-sm text-gray-500">{campaign.campaign_id}</p>
        </div>
        <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
          {campaign.platform}
        </span>
      </div>

      {/* Status Counts */}
      <div className="mt-4 grid grid-cols-4 gap-4">
        <div>
          <p className="text-xs uppercase text-gray-500">Active</p>
          <p className="text-2xl font-bold text-blue-600">
            {status_counts.active_negotiations}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase text-gray-500">Agreed</p>
          <p className="text-2xl font-bold text-green-600">
            {status_counts.agreed}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase text-gray-500">Escalated</p>
          <p className="text-2xl font-bold text-amber-600">
            {status_counts.escalated}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase text-gray-500">Total</p>
          <p className="text-2xl font-bold text-gray-900">
            {status_counts.total_influencers}
          </p>
        </div>
      </div>

      {/* Metrics */}
      <div className="mt-4 grid grid-cols-3 gap-4 border-t pt-4">
        <div>
          <p className="text-xs uppercase text-gray-500">Avg CPM</p>
          <p className="text-lg font-semibold text-gray-900">
            {metrics.avg_cpm_achieved != null
              ? `$${metrics.avg_cpm_achieved.toFixed(2)}`
              : "--"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase text-gray-500">% Closed</p>
          <p className="text-lg font-semibold text-gray-900">
            {metrics.pct_closed.toFixed(1)}%
          </p>
          <div className="mt-1 h-2 rounded-full bg-gray-200">
            <div
              className="h-2 rounded-full bg-green-500"
              style={{ width: `${Math.min(metrics.pct_closed, 100)}%` }}
            />
          </div>
        </div>
        <div>
          <p className="text-xs uppercase text-gray-500">Budget Util</p>
          <p className="text-lg font-semibold text-gray-900">
            {metrics.budget_utilization != null
              ? `${metrics.budget_utilization.toFixed(1)}%`
              : "--"}
          </p>
        </div>
      </div>

      {/* Budget */}
      <p className="mt-3 text-sm text-gray-500">
        Budget: ${campaign.budget.toLocaleString()}
      </p>
    </div>
  );
}
