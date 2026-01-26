import { useEffect, useState } from 'react';
import { mcp2ListServers } from '../services/mcp2AsyncService';

/**
 * Unified MCP2 server options hook.
 *
 * Returns serverKey list in the format `server_name:version`.
 *
 * Note: This is for selection dropdowns (Agent/Graph editor forms).
 */
export const useMCP2ServersOptions = () => {
  const [mcpServers, setMcpServers] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const list = await mcp2ListServers();
        const keys = (list || []).map(s => `${s.server_name}:${s.version}`);
        // stable sort for UX
        keys.sort((a, b) => a.localeCompare(b));
        setMcpServers(keys);
      } catch {
        setMcpServers([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return { mcpServers, loading };
};
