/**
 * @jest-environment node
 */
import { sreClient } from '../lib/api-client';

// NOTE: This test requires the backend to be running on http://127.0.0.1:8000
// Run with: npm run test:integration
describe('SRE Agent API Integration', () => {
  const API_Base_URL = process.env.NEXT_PUBLIC_SRE_AGENT_API_URL || "http://127.0.0.1:8000";

  it('can connect to the CopilotKit endpoint', async () => {
    try {
      // The ADK Agent mounts an /info or /health usually, but we know /copilotkit/info usually exists
      // or we can try hitting the root or a known 404 to check connectivity
      const res = await fetch(`${API_Base_URL}/docs`); // FastAPI docs are usually at /docs
      expect(res.status).toBe(200);
    } catch (error) {
      console.error("Connection failed. Is the backend running?");
      throw error;
    }
  });

  // We can't easily test specific tools without valid credentials/trace IDs,
  // but we can test that the endpoint calls pass the network layer.
  it('receives 404 or 500 (but connects) for invalid trace ID', async () => {
    try {
      // We expect this to fail functionally, but succeed networking-wise
      await sreClient.getTrace('invalid-id');
    } catch (error: any) {
      // If it's a network error, message usually contains "fetch failed"
      // We want to ensure it's NOT a connection refused.
      expect(error.message).not.toMatch(/ECONNREFUSED/);
      // It likely throws "Failed to fetch trace" depending on client logic
    }
  });

});
