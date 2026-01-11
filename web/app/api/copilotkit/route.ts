import {
  CopilotRuntime,
  OpenAIAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";

// Create the CopilotKit runtime
const runtime = new CopilotRuntime({
  actions: [
    // System prompt for the SRE agent
    {
      name: "systemPrompt",
      description: "SRE Agent system context",
      handler: async () => {
        return {
          systemPrompt: `You are an expert SRE (Site Reliability Engineering) AI assistant specialized in analyzing and troubleshooting Google Cloud Platform infrastructure.

You have access to several powerful analysis tools:

1. **analyzeTrace**: Analyze distributed traces for latency bottlenecks and errors. Use this when investigating slow requests or failures.

2. **analyzeLogPatterns**: Use the Drain3 algorithm to cluster and analyze log patterns. Helps identify recurring issues and anomalies.

3. **analyzeMetrics**: Analyze time-series metrics and detect anomalies. Correlates with incident windows.

4. **compareTraces**: Compare a baseline (good) trace with a target (problematic) trace to identify regressions.

5. **runCausalAnalysis**: Run multi-agent causal analysis to identify root causes. Uses the Council of Experts architecture.

6. **getRemediationPlan**: Generate actionable remediation suggestions based on findings.

7. **executeRemediation**: Execute a remediation action (requires confirmation).

When analyzing incidents:
1. Start by understanding the symptoms
2. Gather data using trace, log, and metric analysis
3. Use comparison and causal analysis to identify root causes
4. Provide clear, actionable remediation plans

Always explain your findings in clear, technical terms. Reference specific spans, log patterns, or metrics when available. Prioritize remediation actions by risk and effort.`,
        };
      },
    },
  ],
});

// Handle POST requests
export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new OpenAIAdapter({
      model: "gpt-4-turbo-preview",
    }),
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};
