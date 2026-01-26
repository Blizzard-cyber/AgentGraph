import api from './api';

export interface MCP2ServerInfo {
  server_name: string;
  version: string;
  script_path: string;
  created_at: string;
  updated_at: string;
  owner_user_id?: string;
}

export interface MCP2Tool {
  name: string;
  description: string;
  input_schema: any;
}

export const listMCP2Servers = async (): Promise<MCP2ServerInfo[]> => {
  const res = await api.get('/mcp2/servers');
  return res.data;
};

export const downloadMCP2Server = async (serverName: string, downloadUrl: string) => {
  const res = await api.post('/mcp2/servers/download', {
    server_name: serverName,
    download_url: downloadUrl
  });
  return res.data;
};

export const claimMCP2Server = async (serverName: string, version: string) => {
  const res = await api.post(`/mcp2/servers/${encodeURIComponent(serverName)}/${encodeURIComponent(version)}/claim`);
  return res.data;
};

export const connectMCP2Server = async (serverName: string, version: string, conversationId?: string) => {
  const res = await api.post(`/mcp2/connect/${encodeURIComponent(serverName)}/${encodeURIComponent(version)}`, null, {
    params: { conversation_id: conversationId }
  });
  return res.data as { status: string; server_name: string; version: string; tools: MCP2Tool[] };
};

export const disconnectMCP2Server = async (serverName: string, version: string, conversationId?: string) => {
  const res = await api.post(`/mcp2/disconnect/${encodeURIComponent(serverName)}/${encodeURIComponent(version)}`, null, {
    params: { conversation_id: conversationId }
  });
  return res.data;
};

export const callMCP2Tool = async (
  serverName: string,
  version: string,
  toolName: string,
  params: Record<string, any>,
  conversationId?: string
) => {
  const res = await api.post('/mcp2/tool-call', {
    server_name: serverName,
    version,
    tool_name: toolName,
    params,
    conversation_id: conversationId
  });
  return res.data;
};
