import { create } from 'zustand';
import * as svc from '../services/mcp2AsyncService';

interface MCP2AsyncState {
  tasks: Record<string, svc.MCP2Task>; // key: user_id|server|version
  tools: Record<string, any[]>; // key: server:version
  loading: boolean;
  error?: string;

  addServer: (userId: string, serverKey: string) => Promise<svc.MCP2Task>;
  connect: (userId: string, serverName: string, version: string, conversationId?: string) => Promise<svc.MCP2Task>;
  pollTask: (userId: string, serverName: string, version: string) => Promise<svc.MCP2Task>;
  callTool: (serverName: string, version: string, toolName: string, params: Record<string, any>, conversationId?: string) => Promise<any>;
}

const taskKey = (userId: string, serverName: string, version: string) => `${userId}|${serverName}|${version}`;
const serverKey = (serverName: string, version: string) => `${serverName}:${version}`;

export const useMCP2AsyncStore = create<MCP2AsyncState>((set) => ({
  tasks: {},
  tools: {},
  loading: false,
  error: undefined,

  addServer: async (userId, serverKey) => {
    set({ loading: true, error: undefined });
    const [serverName, version] = (serverKey || '').split(':', 2);
    const res = await svc.mcp2AddServer({ user_id: userId, server_name: serverKey });

    const k = taskKey(userId, serverName, version);
    set((state) => ({
      tasks: { ...state.tasks, [k]: res.task },
      loading: false
    }));

    return res.task;
  },

  connect: async (userId, serverName, version, conversationId) => {
    set({ loading: true, error: undefined });
    const res = await svc.mcp2Connect({ user_id: userId, server_name: serverName, version }, conversationId);

    const k = taskKey(userId, serverName, version);
    set((state) => ({
      tasks: { ...state.tasks, [k]: res.task },
      loading: false
    }));

    // 如果 connect 直接 complete 了，立刻落 tools
    if (res.task.status === 'complete' && res.task.result?.tools) {
      set((state) => ({
        tools: { ...state.tools, [serverKey(serverName, version)]: res.task.result.tools }
      }));
    }

    return res.task;
  },

  pollTask: async (userId, serverName, version) => {
    const t = await svc.mcp2GetTaskStatus({ user_id: userId, server_name: serverName, version });
    const k = taskKey(userId, serverName, version);

    set((state) => ({
      tasks: { ...state.tasks, [k]: t }
    }));

    if (t.task_type === 'connect' && t.status === 'complete' && t.result?.tools) {
      set((state) => ({
        tools: { ...state.tools, [serverKey(serverName, version)]: t.result.tools }
      }));
    }

    return t;
  },

  callTool: async (serverName, version, toolName, params, conversationId) => {
    return await svc.mcp2ToolCall({
      server_name: serverName,
      version,
      tool_name: toolName,
      params,
      conversation_id: conversationId
    });
  }
}));
