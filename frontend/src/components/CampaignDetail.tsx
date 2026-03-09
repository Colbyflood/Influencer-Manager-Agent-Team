import { useState, useEffect, useCallback, useRef } from "react";
import type { CampaignDetailResponse, NegotiationSummary } from "../types/campaign";
import { NegotiationTimeline } from "./NegotiationTimeline";

interface CampaignDetailProps {
  campaignId: string;
  onBack: () => void;
}

const ACTIVE_STATES = new Set([
  "awaiting_reply",
  "counter_sent",
  "counter_received",
  "initial_offer",
]);

const TERMINAL_STATES = new Set(["agreed", "rejected", "stopped"]);

const PAUSABLE_STATES = new Set([
  "awaiting_reply",
  "counter_sent",
  "counter_received",
  "initial_offer",
  "escalated",
  "stale",
]);

function stateBadgeClasses(state: string): string {
  if (state === "agreed") return "bg-green-100 text-green-800";
  if (ACTIVE_STATES.has(state)) return "bg-blue-100 text-blue-800";
  if (state === "escalated") return "bg-amber-100 text-amber-800";
  if (state === "rejected") return "bg-red-100 text-red-800";
  if (state === "paused") return "bg-indigo-100 text-indigo-800";
  if (state === "stopped") return "bg-red-200 text-red-900";
  return "bg-gray-100 text-gray-800";
}

export function CampaignDetail({ campaignId, onBack }: CampaignDetailProps) {
  const [data, setData] = useState<CampaignDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [actionInFlight, setActionInFlight] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/campaigns/${campaignId}/negotiations`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const json = (await res.json()) as CampaignDetailResponse;
      if (!cancelledRef.current) {
        setData(json);
        setError(null);
      }
    } catch (err) {
      if (!cancelledRef.current) {
        setError(err instanceof Error ? err.message : "An unknown error occurred");
      }
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    cancelledRef.current = false;
    fetchDetail();
    return () => { cancelledRef.current = true; };
  }, [fetchDetail]);

  async function handleControl(
    threadId: string,
    action: "pause" | "resume" | "stop",
    event: React.MouseEvent,
  ) {
    event.stopPropagation();
    setActionInFlight(threadId);
    try {
      const res = await fetch(
        `/api/v1/campaigns/${campaignId}/negotiations/${threadId}/${action}`,
        { method: "POST" },
      );
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`HTTP ${res.status}: ${body}`);
      }
      await fetchDetail();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Control action failed");
    } finally {
      setActionInFlight(null);
    }
  }

  if (selectedThreadId) {
    return (
      <NegotiationTimeline
        campaignId={campaignId}
        threadId={selectedThreadId}
        onBack={() => setSelectedThreadId(null)}
      />
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div>
        <button
          onClick={onBack}
          className="mb-4 text-sm font-medium text-blue-600 hover:text-blue-800"
        >
          &larr; Back to campaigns
        </button>
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <p className="font-semibold text-red-800">Error loading negotiations</p>
          <p className="mt-1 text-sm text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={onBack}
        className="mb-4 text-sm font-medium text-blue-600 hover:text-blue-800"
      >
        &larr; Back to campaigns
      </button>

      <h2 className="mb-6 text-xl font-bold text-gray-900">
        Campaign: {campaignId}
      </h2>

      {!data || data.negotiations.length === 0 ? (
        <div className="flex items-center justify-center py-16">
          <div className="rounded-lg border border-gray-200 bg-white px-8 py-6 text-center shadow-sm">
            <p className="text-gray-500">No negotiations found for this campaign</p>
          </div>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Influencer Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  State
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Rate
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Rounds
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Counterparty Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Agency
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {data.negotiations.map((neg: NegotiationSummary) => (
                <tr
                  key={neg.thread_id}
                  onClick={() => setSelectedThreadId(neg.thread_id)}
                  className="cursor-pointer transition-colors hover:bg-gray-50"
                >
                  <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">
                    {neg.influencer_name}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${stateBadgeClasses(neg.state)}`}
                    >
                      {neg.state}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-700">
                    {neg.current_rate != null ? `$${neg.current_rate.toFixed(2)}` : "--"}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-700">
                    {neg.round_count}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-700">
                    {neg.counterparty_type}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-700">
                    {neg.agency_name ?? "--"}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4">
                    <div className="flex gap-2">
                      {PAUSABLE_STATES.has(neg.state) && (
                        <>
                          <button
                            onClick={(e) => handleControl(neg.thread_id, "pause", e)}
                            disabled={actionInFlight === neg.thread_id}
                            className="px-2 py-1 text-xs font-medium rounded bg-amber-100 text-amber-800 hover:bg-amber-200 disabled:opacity-50"
                          >
                            Pause
                          </button>
                          <button
                            onClick={(e) => handleControl(neg.thread_id, "stop", e)}
                            disabled={actionInFlight === neg.thread_id}
                            className="px-2 py-1 text-xs font-medium rounded bg-red-100 text-red-800 hover:bg-red-200 disabled:opacity-50"
                          >
                            Stop
                          </button>
                        </>
                      )}
                      {neg.state === "paused" && (
                        <>
                          <button
                            onClick={(e) => handleControl(neg.thread_id, "resume", e)}
                            disabled={actionInFlight === neg.thread_id}
                            className="px-2 py-1 text-xs font-medium rounded bg-green-100 text-green-800 hover:bg-green-200 disabled:opacity-50"
                          >
                            Resume
                          </button>
                          <button
                            onClick={(e) => handleControl(neg.thread_id, "stop", e)}
                            disabled={actionInFlight === neg.thread_id}
                            className="px-2 py-1 text-xs font-medium rounded bg-red-100 text-red-800 hover:bg-red-200 disabled:opacity-50"
                          >
                            Stop
                          </button>
                        </>
                      )}
                      {TERMINAL_STATES.has(neg.state) && (
                        <span className="text-xs text-gray-400">--</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
