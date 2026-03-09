export interface CampaignStatusCounts {
  active_negotiations: number;
  agreed: number;
  escalated: number;
  rejected: number;
  total_influencers: number;
}

export interface CampaignMetrics {
  avg_cpm_achieved: number | null;
  pct_closed: number;
  budget_utilization: number | null;
}

export interface CampaignSummary {
  campaign_id: string;
  client_name: string;
  platform: string;
  budget: number;
  status_counts: CampaignStatusCounts;
  metrics: CampaignMetrics;
}

export interface CampaignListResponse {
  campaigns: CampaignSummary[];
  total: number;
}
