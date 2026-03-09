import { useState, useEffect } from "react";
import type { TimelineResponse, TimelineEntry as TimelineEntryType } from "../types/campaign";

interface NegotiationTimelineProps {
  campaignId: string;
  threadId: string;
  onBack: () => void;
}

const ACTIVE_STATES = new Set([
  "awaiting_reply",
  "counter_sent",
  "counter_received",
  "initial_offer",
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

function eventBadgeClasses(eventType: string): string {
  if (eventType === "email_sent") return "bg-blue-100 text-blue-800";
  if (eventType === "email_received") return "bg-green-100 text-green-800";
  if (eventType === "state_transition") return "bg-gray-100 text-gray-800";
  if (eventType === "escalation") return "bg-amber-100 text-amber-800";
  if (eventType === "agreement") return "bg-green-200 text-green-900 font-bold";
  return "bg-gray-100 text-gray-700";
}

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

function TimelineEntryCard({ entry }: { entry: TimelineEntryType }) {
  const [expanded, setExpanded] = useState(false);

  const truncatedBody =
    entry.email_body && entry.email_body.length > 200
      ? entry.email_body.slice(0, 200) + "..."
      : entry.email_body;

  const metadata = entry.metadata ?? {};

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-400">{formatTimestamp(entry.timestamp)}</span>
        <span
          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${eventBadgeClasses(entry.event_type)}`}
        >
          {entry.event_type.replace(/_/g, " ")}
        </span>
        {entry.direction && (
          <span className="text-xs text-gray-500">
            {entry.direction === "sent" ? "Sent" : "Received"}
          </span>
        )}
      </div>

      {entry.email_body && (
        <div className="mt-2">
          <p className="text-sm text-gray-700 whitespace-pre-wrap">
            {expanded ? entry.email_body : truncatedBody}
          </p>
          {entry.email_body.length > 200 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1 text-xs font-medium text-blue-600 hover:text-blue-800"
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      )}

      {entry.rates_used && (
        <p className="mt-2 text-xs text-gray-500">
          Rates: {entry.rates_used}
        </p>
      )}

      {entry.event_type === "state_transition" && metadata.from_state && metadata.to_state && (
        <div className="mt-2 flex items-center gap-2 text-xs">
          <span className={`inline-block rounded-full px-2 py-0.5 ${stateBadgeClasses(metadata.from_state)}`}>
            {metadata.from_state}
          </span>
          <span className="text-gray-400">&rarr;</span>
          <span className={`inline-block rounded-full px-2 py-0.5 ${stateBadgeClasses(metadata.to_state)}`}>
            {metadata.to_state}
          </span>
        </div>
      )}
    </div>
  );
}

export function NegotiationTimeline({ campaignId, threadId, onBack }: NegotiationTimelineProps) {
  const [data, setData] = useState<TimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchTimeline() {
      setLoading(true);
      try {
        const res = await fetch(
          `/api/v1/campaigns/${campaignId}/negotiations/${threadId}/timeline`
        );
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        const json = (await res.json()) as TimelineResponse;
        if (!cancelled) {
          setData(json);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "An unknown error occurred");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchTimeline();
    return () => { cancelled = true; };
  }, [campaignId, threadId]);

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
          &larr; Back to negotiations
        </button>
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <p className="font-semibold text-red-800">Error loading timeline</p>
          <p className="mt-1 text-sm text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <button
          onClick={onBack}
          className="mb-4 text-sm font-medium text-blue-600 hover:text-blue-800"
        >
          &larr; Back to negotiations
        </button>
        <div className="flex items-center justify-center py-16">
          <div className="rounded-lg border border-gray-200 bg-white px-8 py-6 text-center shadow-sm">
            <p className="text-gray-500">No timeline data available</p>
          </div>
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
        &larr; Back to negotiations
      </button>

      <h2 className="mb-6 text-xl font-bold text-gray-900">
        {data.influencer_name}
      </h2>

      {/* State Transitions */}
      {data.state_transitions.length > 0 && (
        <div className="mb-8">
          <h3 className="mb-4 text-lg font-semibold text-gray-800">State Transitions</h3>
          <div className="space-y-2">
            {data.state_transitions.map((t, i) => (
              <div key={i} className="flex items-center gap-2">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${stateBadgeClasses(t.from_state)}`}
                >
                  {t.from_state}
                </span>
                <span className="text-xs text-gray-400">&rarr;</span>
                <span className="text-xs font-medium text-gray-600">{t.event}</span>
                <span className="text-xs text-gray-400">&rarr;</span>
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${stateBadgeClasses(t.to_state)}`}
                >
                  {t.to_state}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Activity Timeline */}
      <div>
        <h3 className="mb-4 text-lg font-semibold text-gray-800">Activity Timeline</h3>
        {data.timeline.length === 0 ? (
          <p className="text-sm text-gray-500">No activity recorded yet</p>
        ) : (
          <div className="space-y-3">
            {data.timeline.map((entry, i) => (
              <TimelineEntryCard key={i} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
