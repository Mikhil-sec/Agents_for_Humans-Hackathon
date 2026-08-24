'use client';

import React, { useEffect, useState } from 'react';
import DecisionCard, { Decision } from '@/components/DecisionCard';

const API_BASE = 'http://localhost:8000/api/v1';

export default function Home() {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchDecisions = async () => {
    try {
      const res = await fetch(`${API_BASE}/decisions`);
      if (res.ok) {
        const data = await res.json();
        setDecisions(data);
      }
    } catch (err) {
      console.error('Failed to fetch decision queue:', err);
    } finally {
      setLoading(false);
    }
  };

  const triggerAgentRun = async () => {
    setLoading(true);
    await fetch(`${API_BASE}/agent/run`, { method: 'POST' });
    setTimeout(fetchDecisions, 1000);
  };

  const handleResolve = async (id: string, action: 'approve' | 'reject') => {
    const res = await fetch(`${API_BASE}/decisions/${id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });

    if (res.ok) {
      setDecisions((prev) => prev.filter((item) => item.id !== id));
    }
  };

  useEffect(() => {
    fetchDecisions();
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8 md:p-12">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Agent Decision Inbox</h1>
            <p className="text-slate-400 text-sm mt-1">
              Strands Agents running in background. High-confidence actions surfaced for approval.
            </p>
          </div>
          <button
            onClick={triggerAgentRun}
            className="bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm py-2 px-4 rounded-lg transition-colors"
          >
            Run Agent Scan
          </button>
        </header>

        {/* Action Inbox List */}
        <section>
          {loading ? (
            <div className="text-center py-12 text-slate-500 font-mono">Loading active background tasks...</div>
          ) : decisions.length === 0 ? (
            <div className="text-center py-16 border border-dashed border-slate-800 rounded-xl">
              <p className="text-slate-400 font-medium">Inbox zero! No pending decisions required.</p>
              <p className="text-slate-600 text-xs mt-1">Your background agents are operating normally.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {decisions.map((decision) => (
                <DecisionCard key={decision.id} decision={decision} onResolve={handleResolve} />
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}