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

export interface NegotiationSummary {
  thread_id: string;
  influencer_name: string;
  influencer_email: string;
  state: string;
  round_count: number;
  counterparty_type: string;
  agency_name: string | null;
  current_rate: number | null;
}

export interface CampaignDetailResponse {
  campaign_id: string;
  negotiations: NegotiationSummary[];
  total: number;
}

export interface StateTransition {
  from_state: string;
  event: string;
  to_state: string;
}

export interface TimelineEntry {
  timestamp: string;
  event_type: string;
  direction: string | null;
  email_body: string | null;
  negotiation_state: string | null;
  rates_used: string | null;
  metadata: Record<string, string> | null;
}

export interface TimelineResponse {
  thread_id: string;
  influencer_name: string;
  state_transitions: StateTransition[];
  timeline: TimelineEntry[];
}

export interface ControlResponse {
  thread_id: string;
  action: string;
  previous_state: string;
  new_state: string;
}
