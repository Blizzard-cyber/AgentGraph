// src/App.tsx
import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, App as AntApp } from 'antd';
import enUS from 'antd/locale/en_US';
import zhCN from 'antd/locale/zh_CN';
import WorkspaceLayout from './layouts/WorkspaceLayout';
import PrivateRoute from './components/common/PrivateRoute';
import { isAuthenticated } from './utils/auth';
import { I18nProvider, useI18n } from './i18n';

// Import pages
import Workspace from './pages/Workspace';
import ChatSystem from './pages/ChatSystem';
import GraphEditor from './pages/GraphEditor';
import ModelManager from './pages/ModelManager';
import MCP2Manager from './pages/MCP2Manager';
import PromptManager from './pages/PromptManager';
import AgentManager from './pages/AgentManager';
import SystemToolsManager from './pages/SystemToolsManager';
import ExportManager from './pages/ExportManager';
import TaskManager from './pages/TaskManager';
import TaskDetail from './pages/TaskDetail';
import PreviewPage from './pages/PreviewPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import AdminPanel from './pages/AdminPanel';
import FileManager from './pages/FileManager';
import MemoryManager from './pages/MemoryManager';
import DeviceManagementPage from './pages/DeviceManagementPage';
import SharedConversation from './pages/SharedConversation';

// AppContent component that uses i18n context
const AppContent: React.FC = () => {
  const { locale } = useI18n();
  const antdLocale = locale === 'zh' ? zhCN : enUS;

  useEffect(() => {
    // 设置页面标题
    document.title = "Agent Edge - 自进化云边系统智能底座";
  }, []);

  return (
    <ConfigProvider
      locale={antdLocale}
      theme={{
        token: {
          // 蓝色主题色（与gpustack一致）
          colorPrimary: '#1890ff',
          colorPrimaryHover: '#40a9ff',
          colorPrimaryBorder: '#91caff',
          colorBorder: '#d9d9d9',
          colorBorderSecondary: '#f0f0f0',
          colorText: 'rgba(0, 0, 0, 0.85)',
          colorTextSecondary: 'rgba(0, 0, 0, 0.65)',
          colorTextTertiary: 'rgba(0, 0, 0, 0.45)',
          colorTextPlaceholder: 'rgba(0, 0, 0, 0.25)',
          colorTextDisabled: 'rgba(0, 0, 0, 0.25)',
          colorBgBase: '#ffffff',
          colorBgContainer: '#ffffff',
          colorBgElevated: '#ffffff',
          colorBgLayout: '#ffffff',
          colorError: '#ff4d4f',
          colorErrorBg: '#fff2f0',
          colorSuccess: '#54cc98',
          colorSuccessBg: '#f0fff6',
          colorWarning: '#faad14',
          colorWarningBg: '#fffbe6',
          colorInfo: '#1890ff',
          borderRadius: 4,
          controlHeight: 32,
          fontSize: 14,
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        },
        components: {
          Button: {
            controlHeight: 32,
            borderRadius: 4,
          },
          Input: {
            controlHeight: 32,
            borderRadius: 4,
            activeBorderColor: '#1890ff',
            activeShadow: '0 0 0 2px rgba(24, 144, 255, 0.2)',
          },
          InputNumber: {
            controlHeight: 32,
            borderRadius: 4,
            activeBorderColor: '#1890ff',
            activeShadow: '0 0 0 2px rgba(24, 144, 255, 0.2)',
          },
          Select: {
            controlHeight: 32,
            borderRadius: 4,
            optionSelectedBg: '#e6f4ff',
            optionSelectedFontWeight: 500,
            optionActiveBg: 'rgba(0, 0, 0, 0.04)',
          },
          Dropdown: {
            controlHeight: 32,
            borderRadius: 4,
          },
          Tooltip: {
            borderRadius: 4,
          },
          Modal: {
            borderRadius: 12,
          },
          Card: {
            borderRadius: 4,
          },
          Table: {
            borderRadius: 4,
          },
          Tabs: {
            borderRadius: 4,
          },
          Menu: {
            borderRadius: 4,
          },
        },
      }}
    >
      <AntApp>
        <Router>
      <Routes>
        {/* 公开路由 - 登录和注册 */}
        <Route
          path="/login"
          element={isAuthenticated() ? <Navigate to="/workspace" replace /> : <LoginPage />}
        />
        <Route
          path="/register"
          element={isAuthenticated() ? <Navigate to="/workspace" replace /> : <RegisterPage />}
        />

        {/* 公开路由 - 分享页面（无需登录） */}
        <Route path="/share/:shareId" element={<SharedConversation />} />

        {/* 根路径重定向到工作台 */}
        <Route path="/" element={<Navigate to="/workspace" replace />} />

        {/* 受保护的路由 - 对话系统 */}
        <Route path="/chat" element={
          <PrivateRoute>
            <ChatSystem />
          </PrivateRoute>
        } />
        <Route path="/chat/:conversationId" element={
          <PrivateRoute>
            <ChatSystem />
          </PrivateRoute>
        } />

        {/* 受保护的路由 - 任务管理 */}
        <Route path="/tasks" element={
          <PrivateRoute>
            <TaskManager />
          </PrivateRoute>
        } />
        <Route path="/tasks/:taskId" element={
          <PrivateRoute>
            <TaskDetail />
          </PrivateRoute>
        } />

        {/* 受保护的路由 - 导出管理 */}
        <Route path="/export" element={
          <PrivateRoute>
            <ExportManager />
          </PrivateRoute>
        } />

        {/* 受保护的路由 - 可分享预览页面 */}
        <Route path="/preview" element={
          <PrivateRoute>
            <PreviewPage />
          </PrivateRoute>
        } />

        {/* 受保护的路由 - 工作台入口 */}
        <Route path="/workspace" element={
          <PrivateRoute>
            <Workspace />
          </PrivateRoute>
        } />

        {/* 受保护的路由 - 工作台子页面 */}
        <Route
          path="/workspace/agent-manager"
          element={
            <PrivateRoute>
              <WorkspaceLayout>
                <AgentManager />
              </WorkspaceLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/workspace/graph-editor"
          element={
            <PrivateRoute>
              <WorkspaceLayout>
                <GraphEditor />
              </WorkspaceLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/workspace/model-manager"
          element={
            <PrivateRoute>
              <WorkspaceLayout>
                <ModelManager />
              </WorkspaceLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/workspace/system-tools"
          element={
            <PrivateRoute>
              <WorkspaceLayout>
                <SystemToolsManager />
              </WorkspaceLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/workspace/mcp-manager"
          element={
            <PrivateRoute>
              <WorkspaceLayout>
                <MCP2Manager />
              </WorkspaceLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/workspace/prompt-manager"
          element={
            <PrivateRoute>
              <WorkspaceLayout>
                <PromptManager />
              </WorkspaceLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/workspace/file-manager"
          element={
            <PrivateRoute>
              <WorkspaceLayout>
                <FileManager />
              </WorkspaceLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/workspace/memory-manager"
          element={
            <PrivateRoute>
              <WorkspaceLayout>
                <MemoryManager />
              </WorkspaceLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/workspace/device-management"
          element={
            <PrivateRoute>
              <WorkspaceLayout>
                <DeviceManagementPage />
              </WorkspaceLayout>
            </PrivateRoute>
          }
        />

        {/* 用户管理页面 - 在工作台布局中 */}
        <Route path="/workspace/user-management" element={
          <PrivateRoute>
            <WorkspaceLayout>
              <AdminPanel />
            </WorkspaceLayout>
          </PrivateRoute>
        } />

        {/* 重定向旧路由到新的工作台路由 */}
        <Route path="/graph-editor" element={<Navigate to="/workspace/graph-editor" replace />} />
        <Route path="/model-manager" element={<Navigate to="/workspace/model-manager" replace />} />
        <Route path="/mcp-manager" element={<Navigate to="/workspace/mcp-manager" replace />} />
        <Route path="/prompt-manager" element={<Navigate to="/workspace/prompt-manager" replace />} />

        {/* 默认重定向 */}
        <Route path="*" element={<Navigate to="/workspace" replace />} />
      </Routes>
        </Router>
      </AntApp>
    </ConfigProvider>
  );
};

// Main App component wrapped with I18nProvider
const App: React.FC = () => {
  return (
    <I18nProvider>
      <AppContent />
    </I18nProvider>
  );
};

export default App;
