import React, { useEffect, useMemo, useState } from 'react';
import { Layout, Row, Col, Alert, App, Modal, Form, Input } from 'antd';
import { Grid3x3 } from 'lucide-react';

import MCPServerCard from '../components/mcp-manager/MCPServerCard';
import MCPToolsViewer from '../components/mcp-manager/MCPToolsViewer';
import MCPManagerHeader from '../components/mcp-manager/MCPManagerHeader';
import MCPActionButtons from '../components/mcp-manager/MCPActionButtons';
import { MCP_COLORS, getMCPEmptyStateStyle } from '../constants/mcpManagerStyles';
import { useT } from '../i18n/hooks';
import { getUserInfo } from '../utils/auth';

import { MCPServerConfig } from '../types/mcp';
import { useMCP2AsyncStore } from '../store/mcp2AsyncStore';
import { mcp2GetTaskStatus, mcp2Disconnect, mcp2ListServers } from '../services/mcp2AsyncService';
import { mcp2RemoveServer } from '../services/mcp2AsyncService';
import { mcp2UpdateServer } from '../services/mcp2AsyncService';
import type { MCP2Tool } from '../types/mcp2';
import { updateZustandState } from '../store/zustandUtils';

const { Content } = Layout;

// A lightweight local config adapter to reuse existing MCPServerCard UI
const buildCardConfig = (serverName: string): MCPServerConfig => ({
  autoApprove: [],
  disabled: false,
  timeout: 60,
  command: 'python',
  args: [serverName],
  transportType: 'stdio',
});

const serverKey = (name: string, version: string) => `${name}:${version}`;

const MCP2Manager: React.FC = () => {
  const t = useT();
  const { message } = App.useApp();
  const currentUser = getUserInfo();

  const {
    addServer,
    connect,
    pollTask,
    tools,
    loading,
    error,
  } = useMCP2AsyncStore();

  const [servers, setServers] = useState<Array<{ server_name: string; version: string; download_url?: string }>>([]);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [addForm] = Form.useForm();

  const [toolsModalVisible, setToolsModalVisible] = useState(false);
  const [selectedServer, setSelectedServer] = useState<string>('');

  const [connectErrors, setConnectErrors] = useState<Record<string, string | undefined>>({});
  const [connectStates, setConnectStates] = useState<Record<string, 'idle' | 'connecting' | 'connected' | 'error'>>({});

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingServer, setEditingServer] = useState<string>('');
  const [editForm] = Form.useForm();

  const selectedTools: MCP2Tool[] = tools[selectedServer] || [];

  const connectedCount = useMemo(() => {
    // Connected = tools loaded for that server
    return servers.filter(s => (tools[serverKey(s.server_name, s.version)] || []).length > 0).length;
  }, [servers, tools]);

  useEffect(() => {
    const load = async () => {
      try {
        const list = await mcp2ListServers();
        setServers(list.map(s => ({ server_name: s.server_name, version: s.version, download_url: s.download_url })));

        // hydrate task/tool state after refresh
        const userId = currentUser?.user_id;
        if (userId) {
          for (const s of list) {
            const k = serverKey(s.server_name, s.version);

            // IMPORTANT: runtime connection truth comes from backend list (client_table),
            // not from task_table. A connect task can stay "complete" even after disconnect.
            setConnectStates(prev => ({ ...prev, [k]: s.connected ? 'connected' : 'idle' }));
            setConnectErrors(prev => ({ ...prev, [k]: undefined }));

            try {
              const task = await mcp2GetTaskStatus({ user_id: userId, server_name: s.server_name, version: s.version });
              if (task.task_type === 'connect') {
                // Only use task_table for transient status/error (NOT as source of truth for connected)
                if (task.status === 'started' || task.status === 'connecting') {
                  setConnectStates(prev => ({ ...prev, [k]: 'connecting' }));
                } else if (task.status === 'error') {
                  setConnectStates(prev => ({ ...prev, [k]: 'error' }));
                  setConnectErrors(prev => ({ ...prev, [k]: task.message || 'Connect failed' }));
                }
              }
              // eslint-disable-next-line @typescript-eslint/no-unused-vars
            } catch (e) {
              // task might not exist after backend restart; treat as idle/unconnected
              // keep state from /servers
            }

            // If currently connected and we have tools in task result, hydrate tools.
            // This is only for displaying tool list; connection truth still comes from s.connected.
            if (s.connected) {
              try {
                const task = await mcp2GetTaskStatus({ user_id: userId, server_name: s.server_name, version: s.version });
                if (task.task_type === 'connect' && task.status === 'complete' && task.result?.tools) {
                  updateZustandState(useMCP2AsyncStore, (state: any) => {
                    const next = { ...state.tools };
                    next[k] = task.result.tools;
                    return { tools: next };
                  });
                }
              } catch {
                // ignore
              }
            } else {
              // not connected => ensure tools cache doesn't force UI to show connected
              updateZustandState(useMCP2AsyncStore, (state: any) => {
                const next = { ...state.tools };
                delete next[k];
                return { tools: next };
              });
            }
          }
        }
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
      } catch (e) {
        // ignore
      }
    };
    load();
  }, []);

  const openAddModal = () => {
    setAddModalOpen(true);
    addForm.resetFields();
  };

  const refreshServers = async () => {
    const userId = currentUser?.user_id;
    const list = await mcp2ListServers();
    setServers(list.map(s => ({ server_name: s.server_name, version: s.version, download_url: s.download_url })));

    // default everything to idle + clear error on refresh; only set error when backend explicitly reports it
    const nextStates: Record<string, 'idle' | 'connecting' | 'connected' | 'error'> = {};
    const nextErrors: Record<string, string | undefined> = {};

    if (userId) {
      for (const s of list) {
        const k = serverKey(s.server_name, s.version);
        // IMPORTANT: runtime connection truth comes from backend list (client_table)
        nextStates[k] = s.connected ? 'connected' : 'idle';
        nextErrors[k] = undefined;
        try {
          const task = await mcp2GetTaskStatus({ user_id: userId, server_name: s.server_name, version: s.version });
          if (task.task_type === 'connect') {
            // Only transient statuses/errors from task_table
            if (task.status === 'started' || task.status === 'connecting') {
              nextStates[k] = 'connecting';
            } else if (task.status === 'error') {
              nextStates[k] = 'error';
              nextErrors[k] = task.message || 'Connect failed';
            }
          }
        } catch (e) {
          // ignore missing task after restart
        }

        // Hydrate/clear tools based on current runtime connection
        if (s.connected) {
          try {
            const task = await mcp2GetTaskStatus({ user_id: userId, server_name: s.server_name, version: s.version });
            if (task.task_type === 'connect' && task.status === 'complete' && task.result?.tools) {
              updateZustandState(useMCP2AsyncStore, (state: any) => {
                const next = { ...state.tools };
                next[k] = task.result.tools;
                return { tools: next };
              });
            }
          } catch {
            // ignore
          }
        } else {
          updateZustandState(useMCP2AsyncStore, (state: any) => {
            const next = { ...state.tools };
            delete next[k];
            return { tools: next };
          });
        }
      }
    }

    setConnectStates(nextStates);
    setConnectErrors(nextErrors);
  };

  const connectAllServers = async () => {
    const userId = currentUser?.user_id;
    if (!userId) {
      message.error('Missing user_id');
      return;
    }

    const targets = servers
      .map(s => serverKey(s.server_name, s.version))
      .filter(k => connectStates[k] !== 'connected' && connectStates[k] !== 'connecting');

    if (targets.length === 0) {
      message.info(t('pages.mcpManager.connectAllNone'));
      return;
    }

    message.info(t('pages.mcpManager.connectAllLoading'));

    // Track final results locally to avoid relying on async React state updates
    const finalStatus: Record<string, 'pending' | 'connected' | 'error'> = {};
    for (const k of targets) finalStatus[k] = 'pending';

    for (const k of targets) {
      const [server_name, version] = k.split(':');
      try {
        setConnectErrors(prev => ({ ...prev, [k]: undefined }));
        setConnectStates(prev => ({ ...prev, [k]: 'connecting' }));
        await connect(userId, server_name, version);
      } catch (e) {
        // ignore: polling will capture error
      }
    }

    // poll all
    for (let i = 0; i < 5; i++) {
      let done = 0;
      for (const k of targets) {
        if (finalStatus[k] !== 'pending') {
          done += 1;
          continue;
        }
        const [server_name, version] = k.split(':');
        try {
          const task = await pollTask(userId, server_name, version);
          if (task.status === 'complete') {
            setConnectStates(prev => ({ ...prev, [k]: 'connected' }));
            setConnectErrors(prev => ({ ...prev, [k]: undefined }));
            finalStatus[k] = 'connected';
            done += 1;
          } else if (task.status === 'error') {
            setConnectStates(prev => ({ ...prev, [k]: 'error' }));
            setConnectErrors(prev => ({ ...prev, [k]: task.message || 'Connect failed' }));
            finalStatus[k] = 'error';
            done += 1;
          }
        } catch (e) {
          // ignore
        }
      }
      if (done === targets.length) break;
      await new Promise(r => setTimeout(r, 10000));
    }

    // tally success/fail from finalStatus first; fall back to tools cache if task result arrived late
    let success = 0;
    let failed = 0;
    for (const k of targets) {
      if (finalStatus[k] === 'connected') {
        success += 1;
      } else if (finalStatus[k] === 'error') {
        failed += 1;
      } else {
        // pending (timeout): if tools already exist, treat as success
        if ((tools[k] || []).length > 0) success += 1;
        else failed += 1;
      }
    }

    if (success > 0 && failed === 0) {
      message.success(t('pages.mcpManager.connectAllSuccess', { count: success }));
    } else if (success > 0 && failed > 0) {
      message.warning(t('pages.mcpManager.connectAllPartial', { success, failed }));
    } else {
      message.error(t('pages.mcpManager.connectAllFailed', { count: targets.length }));
    }
  };

  const handleConnect = async (key: string) => {
    const userId = currentUser?.user_id;
    if (!userId) {
      message.error('Missing user_id');
      return;
    }

    const [server_name, version] = key.split(':');
    // clear previous error
    setConnectErrors(prev => ({ ...prev, [key]: undefined }));
    setConnectStates(prev => ({ ...prev, [key]: 'connecting' }));

    await connect(userId, server_name, version);

    for (let i = 0; i < 5; i++) {
      const task = await pollTask(userId, server_name, version);
      if (task.status === 'complete') {
        message.success(t('pages.mcpManager.connectSuccess', { name: key }));
        setConnectErrors(prev => ({ ...prev, [key]: undefined }));
        setConnectStates(prev => ({ ...prev, [key]: 'connected' }));
        return;
      }
      if (task.status === 'error') {
        const msg = task.message || 'Connect failed';
        message.error(msg);
        setConnectErrors(prev => ({ ...prev, [key]: msg }));
        setConnectStates(prev => ({ ...prev, [key]: 'error' }));
        return;
      }
      await new Promise(r => setTimeout(r, 10000));
    }

    message.info('Connecting...');
  };

  const handleDisconnect = async (key: string) => {
    const userId = currentUser?.user_id;
    if (!userId) {
      message.error('Missing user_id');
      return;
    }
    const [server_name, version] = key.split(':');
    try {
      await mcp2Disconnect({ user_id: userId, server_name, version });

      // keep server in list; just reset connection state
      setConnectStates(prev => ({ ...prev, [key]: 'idle' }));
      setConnectErrors(prev => ({ ...prev, [key]: undefined }));

      updateZustandState(useMCP2AsyncStore, (state: any) => {
        const next = { ...state.tools };
        delete next[key];
        return { tools: next };
      });

      message.success(t('pages.mcpManager.disconnectSuccess', { name: key }));
    } catch (e: any) {
      message.error(e?.message || 'Disconnect failed');
    }
  };

  const handleEdit = (key: string) => {
    const [server_name, version] = key.split(':');
    setEditingServer(key);
    setEditModalOpen(true);
    editForm.setFieldsValue({ server_name, version });
  };

  const submitEdit = async () => {
    const userId = currentUser?.user_id;
    if (!userId) {
      message.error('Missing user_id');
      return;
    }

    const values = await editForm.validateFields();
    const { server_name, version } = values as any;
    const [old_name, old_version] = editingServer.split(':');

    // disconnect old before update to keep frontend/backend consistent
    try {
      await mcp2Disconnect({ user_id: userId, server_name: old_name, version: old_version });
    } catch (e) {
      // ignore
    }

    await mcp2UpdateServer({
      user_id: userId,
      old_server_name: old_name,
      old_version,
      new_server_name: server_name,
      new_version: version,
    });

    // refresh list
    const list = await mcp2ListServers();
    setServers(list.map(s => ({ server_name: s.server_name, version: s.version, download_url: s.download_url })));

    // reset old/new keys to idle (not connected) after update
    const oldKey = `${old_name}:${old_version}`;
    const newKey = `${server_name}:${version}`;

    setConnectStates(prev => ({ ...prev, [oldKey]: 'idle', [newKey]: 'idle' }));
    setConnectErrors(prev => ({ ...prev, [oldKey]: undefined, [newKey]: undefined }));

    updateZustandState(useMCP2AsyncStore, (state: any) => {
      const nextTools = { ...state.tools };
      delete nextTools[oldKey];
      delete nextTools[newKey];
      return { tools: nextTools };
    });

    setEditModalOpen(false);
    message.success('Updated');
  };

  const submitAdd = async () => {
    const userId = currentUser?.user_id;
    if (!userId) {
      message.error('Missing user_id');
      return;
    }

    const values = await addForm.validateFields();
    const { server_name, version } = values as any;
    const key = serverKey(server_name, version);

    await addServer(userId, `${server_name}:${version}`);

    // poll add task
    for (let i = 0; i < 5; i++) {
      const task = await mcp2GetTaskStatus({ user_id: userId, server_name, version });
      if (task.status === 'complete') {
        message.success(t('pages.mcpManager.serverAddSuccess', { name: key }));

        setServers((prev) => {
          if (prev.some(p => serverKey(p.server_name, p.version) === key)) return prev;
          return [...prev, { server_name, version }];
        });

        // Only reset to idle if not already connected (avoid overwriting connected state)
        const alreadyConnected = connectStates[key] === 'connected' || (tools[key] || []).length > 0;
        if (!alreadyConnected) {
          setConnectStates(prev => ({ ...prev, [key]: 'idle' }));
          setConnectErrors(prev => ({ ...prev, [key]: undefined }));
          updateZustandState(useMCP2AsyncStore, (state: any) => {
            const next = { ...state.tools };
            delete next[key];
            return { tools: next };
          });
        }

        setAddModalOpen(false);
        return;
      }
      if (task.status === 'error') {
        message.error(task.message || 'Add server failed');
        return;
      }
      await new Promise(r => setTimeout(r, 10000));
    }

    message.info('Downloading...');
  };

  const handleViewTools = (key: string) => {
    setSelectedServer(key);
    setToolsModalVisible(true);
  };

  const handleDelete = async (key: string) => {
    const userId = currentUser?.user_id;
    if (!userId) {
      message.error('Missing user_id');
      return;
    }

    const [server_name, version] = key.split(':');

    try {
      await mcp2RemoveServer({ user_id: userId, server_name, version });

      // remove from local list and clear cached tools
      setServers(prev => prev.filter(s => serverKey(s.server_name, s.version) !== key));
      updateZustandState(useMCP2AsyncStore, (state: any) => {
        const next = { ...state.tools };
        delete next[key];
        return { tools: next };
      });

      // clear local connection error/state so re-add won't inherit "failed" badge
      setConnectStates(prev => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      setConnectErrors(prev => {
        const next = { ...prev };
        delete next[key];
        return next;
      });

      message.success(t('pages.mcpManager.serverDeleteSuccess', { name: key }));
    } catch (e: any) {
      message.error(e?.message || 'Remove failed');
    }
  };

  const serverKeys = servers.map(s => serverKey(s.server_name, s.version));

  return (
    <Layout style={{ height: '100vh', background: MCP_COLORS.background, display: 'flex', flexDirection: 'column' }}>
      <MCPManagerHeader
        title={'MCP 管理'}
        serversCount={serverKeys.length}
        connectedCount={connectedCount}
        viewMode={'visual'}
        onViewModeChange={() => { }}
        t={t}
      />

      <Content style={{ flex: 1, padding: '32px 48px', overflow: 'auto' }}>
        {error && (
          <Alert
            message={t('common.error')}
            description={error}
            type="error"
            showIcon
            style={{ marginBottom: '16px', borderRadius: '6px' }}
          />
        )}

        <MCPActionButtons
          onAddServer={openAddModal}
          onRefresh={refreshServers}
          onConnectAll={connectAllServers}
          loading={loading}
          disabled={serverKeys.length === 0}
          t={t}
        />

        {serverKeys.length === 0 ? (
          <div style={getMCPEmptyStateStyle()}>
            <Grid3x3 size={48} strokeWidth={1.5} style={{ color: 'rgba(24, 144, 255, 0.3)', margin: '0 auto 16px' }} />
            <div style={{ fontSize: '14px', color: MCP_COLORS.textSecondary, marginBottom: '8px' }}>
              {t('pages.mcpManager.noServers')}
            </div>
          </div>
        ) : (
          <Row gutter={[12, 12]}>
            {serverKeys.map(key => (
              <Col xs={24} lg={24} xl={12} key={key}>
                <MCPServerCard
                  serverName={key}
                  config={buildCardConfig(key)}
                  status={{
                    connected: connectStates[key] === 'connected' || (tools[key] || []).length > 0,
                    connecting: connectStates[key] === 'connecting',
                    init_attempted: Boolean(connectErrors[key]),
                    tools: (tools[key] || []).map(t => t.name),
                    error: connectErrors[key],
                  }}
                  onConnect={() => handleConnect(key)}
                  onDisconnect={() => handleDisconnect(key)}
                  onEdit={() => handleEdit(key)}
                  onDelete={() => handleDelete(key)}
                  onViewTools={() => handleViewTools(key)}
                  loading={loading}
                  currentUserId={currentUser?.user_id}
                  currentUserRole={currentUser?.role}
                />
              </Col>
            ))}
          </Row>
        )}

        <Modal
          open={addModalOpen}
          onCancel={() => setAddModalOpen(false)}
          onOk={submitAdd}
          title={t('pages.mcpManager.addServerTitle')}
        >
          <Form form={addForm} layout="vertical">
            <Form.Item name="server_name" label="server_name" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="version" label="version" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            {/* download_url is resolved by backend via FILE_SYSTEM */}
          </Form>
        </Modal>

        <Modal
          open={editModalOpen}
          onCancel={() => setEditModalOpen(false)}
          onOk={submitEdit}
          title={t('pages.mcpManager.editServerTitle', { name: editingServer || '' })}
        >
          <Form form={editForm} layout="vertical">
            <Form.Item name="server_name" label="server_name" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="version" label="version" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
          </Form>
        </Modal>

        <MCPToolsViewer
          visible={toolsModalVisible}
          onClose={() => setToolsModalVisible(false)}
          serverName={selectedServer}
          tools={selectedTools}
        />
      </Content>
    </Layout>
  );
};

export default MCP2Manager;
