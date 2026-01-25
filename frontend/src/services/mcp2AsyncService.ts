import api from './api';

export type MCP2TaskType = 'add_server' | 'connect';
export type MCP2TaskStatus = 'started' | 'downloading' | 'connecting' | 'complete' | 'error';

export interface MCP2TaskKey {
  user_id: string;
  server_name: string;
  version: string;
}

export interface MCP2Task {
  key: MCP2TaskKey;
  task_type: MCP2TaskType;
  status: MCP2TaskStatus | string;
  message?: string;
  updated_at: string;
  result?: any;
}

export const mcp2AddServer = async (payload: {
  user_id: string;
  server_name: string; // serverKey: name:version
}) => {
  const res = await api.post('/mcp2/add-server', payload);
  return res.data as { status: 'accepted'; task: MCP2Task };
};

export const mcp2Connect = async (payload: MCP2TaskKey, conversationId?: string) => {
  const res = await api.post('/mcp2/connect', payload, {
    params: { conversation_id: conversationId }
  });
  return res.data as { status: 'accepted'; task: MCP2Task };
};

export const mcp2GetTaskStatus = async (params: MCP2TaskKey) => {
  const res = await api.get('/mcp2/tasks/status', { params });
  return res.data as MCP2Task;
};

export const mcp2ToolCall = async (payload: {
  server_name: string;
  version: string;
  tool_name: string;
  params: Record<string, any>;
  conversation_id?: string;
}) => {
  const res = await api.post('/mcp2/tool-call', payload);
  return res.data;
};

export const mcp2Disconnect = async (payload: {
  user_id: string;
  server_name: string;
  version: string;
  conversation_id?: string;
}) => {
  const res = await api.post('/mcp2/disconnect', payload);
  return res.data;
};

export const mcp2RemoveServer = async (payload: {
  user_id: string;
  server_name: string;
  version: string;
}) => {
  const res = await api.post('/mcp2/servers/remove', payload);
  return res.data;
};

export const mcp2ListServers = async () => {
  const res = await api.get('/mcp2/servers');
  return res.data as Array<{
    server_name: string;
    version: string;
    added_at?: string;
    download_url?: string;
    connected?: boolean;
    tools_count?: number;
  }>;
};

export const mcp2UpdateServer = async (payload: {
  user_id: string;
  old_server_name: string;
  old_version: string;
  new_server_name: string;
  new_version: string;
}) => {
  const res = await api.post('/mcp2/servers/update', payload);
  return res.data;
};
