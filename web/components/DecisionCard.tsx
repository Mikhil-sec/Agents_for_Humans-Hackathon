'use client';

import React, { useState } from 'react';

export interface DecisionPayload {
  [key: string]: string | number | boolean;
}

export interface Decision {
  id: string;
  event_id: string;
  title: string;
  description: string;
  suggested_action: string;
  payload: DecisionPayload;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  created_at: string;
}

interface DecisionCardProps {
  decision: Decision;
  onResolve: (id: string, action: 'approve' | 'reject') => Promise<void>;
}

export default function DecisionCard({ decision, onResolve }: DecisionCardProps) {
  const [loading, setLoading] = useState(false);

  const handleAction = async (action: 'approve' | 'reject') => {
    setLoading(true);
    try {
      await onResolve(decision.id, action);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg hover:border-slate-700 transition-all">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono bg-blue-950 text-blue-400 border border-blue-800/50 px-2.5 py-1 rounded-full uppercase tracking-wider">
          Action Required
        </span>
        <span className="text-xs text-slate-500 font-mono">
          {new Date(decision.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>

      <h3 className="text-lg font-semibold text-slate-100 mb-2">{decision.title}</h3>
      <p className="text-slate-400 text-sm mb-4 leading-relaxed">{decision.description}</p>

      {/* Structured Payload Breakdown */}
      {decision.payload && Object.keys(decision.payload).length > 0 && (
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 mb-4 space-y-1.5 font-mono text-xs">
          {Object.entries(decision.payload).map(([key, value]) => (
            <div key={key} className="flex justify-between text-slate-300">
              <span className="text-slate-500 capitalize">{key.replace(/_/g, ' ')}:</span>
              <span className="font-medium text-slate-200">{String(value)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Agent's Recommendation */}
      <div className="bg-amber-950/20 border border-amber-900/40 rounded-lg p-3.5 mb-5">
        <span className="text-xs font-semibold text-amber-400 uppercase tracking-wide block mb-1">
          Agent Proposal
        </span>
        <p className="text-sm text-amber-200/90 font-medium">{decision.suggested_action}</p>
      </div>

      {/* Interactive Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => handleAction('approve')}
          disabled={loading}
          className="flex-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium text-sm py-2.5 px-4 rounded-lg transition-colors focus:ring-2 focus:ring-emerald-500/40 outline-none"
        >
          {loading ? 'Processing...' : 'Approve Action'}
        </button>
        <button
          onClick={() => handleAction('reject')}
          disabled={loading}
          className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 hover:text-white font-medium text-sm py-2.5 px-4 rounded-lg border border-slate-700 transition-colors focus:ring-2 focus:ring-slate-600/40 outline-none"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}