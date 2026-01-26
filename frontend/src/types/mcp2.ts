export interface MCP2Server {
  server_name: string;
  version: string;
  script_path?: string;
  created_at?: string;
  updated_at?: string;
}

export interface MCP2TaskKey {
  user_id: string;
  server_name: string;
  version: string;
}

export interface MCP2Task {
  key: MCP2TaskKey;
  task_type: 'add_server' | 'connect' | string;
  status: 'started' | 'downloading' | 'connecting' | 'complete' | 'error' | string;
  message?: string;
  updated_at: string;
  result?: any;
}

export interface MCP2Tool {
  name: string;
  description: string;
  input_schema: any;
}
