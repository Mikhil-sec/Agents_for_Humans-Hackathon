# System Architecture

The agent ecosystem operates on an event-driven background loop with human-in-the-loop validation:

```text
 ┌──────────────────────────────────┐
 │ External Triggers / Data Feeds   │
 │ (Emails, Invoices, Stock Scans)  │
 └─────────────────┬────────────────┘
                   │
                   ▼
 ┌──────────────────────────────────┐
 │ Strands Agent Engine (Python SDK)│ ──► [ Model Context Protocol (MCP) Tools ]
 │ Executing on AWS AgentCore       │
 └─────────────────┬────────────────┘
                   │ High-Confidence Action / Exception Identified
                   ▼
 ┌──────────────────────────────────┐
 │ FastAPI Control Layer (`/api/v1`)│
 │ Decision Queue & State Manager   │
 └─────────────────┬────────────────┘
                   │ Real-time Event Push
                   ▼
 ┌──────────────────────────────────┐
 │ Next.js Decision Inbox UI        │
 │ (`DecisionCard.tsx`)             │
 └──────────────────────────────────┘