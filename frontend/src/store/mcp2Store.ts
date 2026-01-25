import { create } from 'zustand';
import * as mcp2Service from '../services/mcp2Service';

interface MCP2State {
  servers: mcp2Service.MCP2ServerInfo[];
  tools: Record<string, mcp2Service.MCP2Tool[]>; // key: `${server_name}:${version}`
  loading: boolean;
  error?: string;

  fetchServers: () => Promise<void>;
  addServerByDownload: (serverName: string, downloadUrl: string) => Promise<void>;
  connect: (serverName: string, version: string, conversationId?: string) => Promise<void>;
  disconnect: (serverName: string, version: string, conversationId?: string) => Promise<void>;
  callTool: (serverName: string, version: string, toolName: string, params: Record<string, any>, conversationId?: string) => Promise<any>;
}

const keyOf = (serverName: string, version: string) => `${serverName}:${version}`;

export const useMCP2Store = create<MCP2State>((set, get) => ({
  servers: [],
  tools: {},
  loading: false,
  error: undefined,

  fetchServers: async () => {
    try {
      set({ loading: true, error: undefined });
      const servers = await mcp2Service.listMCP2Servers();
      set({ servers, loading: false });
    } catch (e) {
      set({ loading: false, error: e instanceof Error ? e.message : 'Failed to fetch servers' });
    }
  },

  addServerByDownload: async (serverName, downloadUrl) => {
    try {
      set({ loading: true, error: undefined });
      await mcp2Service.downloadMCP2Server(serverName, downloadUrl);
      await get().fetchServers();
      set({ loading: false });
    } catch (e) {
      set({ loading: false, error: e instanceof Error ? e.message : 'Failed to add server' });
      throw e;
    }
  },

  connect: async (serverName, version, conversationId) => {
    try {
      set({ loading: true, error: undefined });
      const res = await mcp2Service.connectMCP2Server(serverName, version, conversationId);
      set((state) => ({
        tools: {
          ...state.tools,
          [keyOf(serverName, version)]: res.tools
        },
        loading: false
      }));
    } catch (e) {
      set({ loading: false, error: e instanceof Error ? e.message : 'Failed to connect' });
      throw e;
    }
  },

  disconnect: async (serverName, version, conversationId) => {
    try {
      set({ loading: true, error: undefined });
      await mcp2Service.disconnectMCP2Server(serverName, version, conversationId);
      set((state) => {
        const next = { ...state.tools };
        delete next[keyOf(serverName, version)];
        return { tools: next, loading: false };
      });
    } catch (e) {
      set({ loading: false, error: e instanceof Error ? e.message : 'Failed to disconnect' });
      throw e;
    }
  },

  callTool: async (serverName, version, toolName, params, conversationId) => {
    return await mcp2Service.callMCP2Tool(serverName, version, toolName, params, conversationId);
  }
}));
