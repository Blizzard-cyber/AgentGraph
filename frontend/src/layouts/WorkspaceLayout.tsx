// src/layouts/WorkspaceLayout.tsx
import React, { useState, useEffect, CSSProperties } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Button, Tooltip } from 'antd';
import {
  Bot,
  Network,
  Cpu,
  Wrench,
  Plug,
  MessageSquareText,
  FolderOpen,
  Database,
  Home,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { useT } from '../i18n';
import UserMenu from '../components/common/UserMenu';
import { useTour, workspaceTourSteps } from '../components/tour';
import '../components/tour/tour-custom.css';

interface WorkspaceLayoutProps {
  children: React.ReactNode;
}

const WorkspaceLayout: React.FC<WorkspaceLayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const t = useT();
  const [collapsed, setCollapsed] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  // 引导演示 - 首次访问自动启动
  const { startTour } = useTour({
    steps: workspaceTourSteps,
    onComplete: () => {
      localStorage.setItem('workspace-tour-completed', 'true');
    },
    onSkip: () => {
      localStorage.setItem('workspace-tour-completed', 'true');
    }
  });

  // 首次访问时自动启动引导
  useEffect(() => {
    const tourCompleted = localStorage.getItem('workspace-tour-completed');
    if (!tourCompleted) {
      // 延迟启动，确保页面完全加载
      const timer = setTimeout(() => {
        startTour();
      }, 1000);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 只在组件挂载时执行一次

  const navItems = [
    { path: '/workspace/agent-manager', icon: Bot, labelKey: 'pages.workspace.agentManager', tourId: 'workspace-agent-manager' },
    { path: '/workspace/graph-editor', icon: Network, labelKey: 'pages.workspace.graphEditor', tourId: 'workspace-graph-editor' },
    { path: '/workspace/model-manager', icon: Cpu, labelKey: 'pages.workspace.modelManager', tourId: 'workspace-model-manager' },
    { path: '/workspace/system-tools', icon: Wrench, labelKey: 'pages.workspace.systemTools', tourId: 'workspace-system-tools' },
    { path: '/workspace/mcp-manager', icon: Plug, labelKey: 'pages.workspace.mcpManager', tourId: 'workspace-mcp-manager' },
    { path: '/workspace/prompt-manager', icon: MessageSquareText, labelKey: 'pages.workspace.promptManager', tourId: 'workspace-prompt-manager' },
    { path: '/workspace/file-manager', icon: FolderOpen, labelKey: 'pages.workspace.fileManager', tourId: 'workspace-file-manager' },
    { path: '/workspace/memory-manager', icon: Database, labelKey: 'pages.workspace.memoryManager', tourId: 'workspace-memory-manager' },
  ];

  // 侧边栏容器样式
  const sidebarStyle: CSSProperties = {
    width: collapsed ? '72px' : '280px',
    minHeight: '100vh',
    background: '#ffffff',
    borderRight: '1px solid #d9d9d9',
    boxShadow: 'none',
    display: 'flex',
    flexDirection: 'column',
    transition: 'width 0.4s cubic-bezier(0.23, 1, 0.32, 1)',
    position: 'relative',
    overflow: 'hidden'
  };

  // Header 样式
  const headerStyle: CSSProperties = {
    padding: collapsed ? '24px 0' : '24px 20px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: collapsed ? 'center' : 'space-between',
    borderBottom: '1px solid #d9d9d9',
    background: '#fff',
    position: 'relative'
  };

  const headerDecorStyle: CSSProperties = {
    display: 'none'
  };

  const titleStyle: CSSProperties = {
    fontSize: '15px',
    fontWeight: 500,
    color: '#2d2d2d',
    margin: 0,
    letterSpacing: '0.5px',
    opacity: collapsed ? 0 : 1,
    transition: 'opacity 0.3s ease',
    whiteSpace: 'nowrap'
  };

  // 导航区域样式
  const navigationStyle: CSSProperties = {
    flex: 1,
    padding: collapsed ? '20px 12px' : '20px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    overflowY: 'auto',
    overflowX: 'hidden'
  };

  const getNavItemStyle = (isActive: boolean, isHovered: boolean): CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    gap: collapsed ? '0' : '12px',
    padding: collapsed ? '12px' : '12px 16px',
    borderRadius: '4px',
    textDecoration: 'none',
    transition: 'all 0.3s cubic-bezier(0.23, 1, 0.32, 1)',
    position: 'relative',
    justifyContent: collapsed ? 'center' : 'flex-start',
    background: isActive 
      ? '#e6f4ff'
      : isHovered 
        ? 'rgba(0, 0, 0, 0.04)'
        : 'transparent',
    border: `1px solid transparent`,
    boxShadow: 'none',
    color: isActive ? '#1890ff' : 'rgba(0, 0, 0, 0.85)',
    transform: 'none'
  });

  const navLabelStyle: CSSProperties = {
    fontSize: '14px',
    fontWeight: 500,
    letterSpacing: '0.3px',
    opacity: collapsed ? 0 : 1,
    transition: 'opacity 0.3s ease',
    whiteSpace: 'nowrap'
  };

  // Footer 样式
  const footerStyle: CSSProperties = {
    padding: collapsed ? '20px 12px' : '20px 16px',
    borderTop: '1px solid #d9d9d9',
    background: '#fff',
    display: 'flex',
    flexDirection: collapsed ? 'column' : 'row',
    gap: '8px',
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative'
  };

  const footerDecorStyle: CSSProperties = {
    display: 'none'
  };

  return (
    <>
      <style>
        {`
          @keyframes gentleFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
          }
        `}
      </style>

      <div style={{ display: 'flex', minHeight: '100vh', background: '#ffffff' }}>
        {/* 侧边栏 */}
        <div style={sidebarStyle} data-tour="workspace-sidebar">
          {/* Header */}
          <div style={headerStyle}>
            <div style={headerDecorStyle} />
            {!collapsed && <h3 style={titleStyle}>{t('pages.workspace.title')}</h3>}
            <Button
              type="text"
              icon={collapsed ? <ChevronRight size={16} strokeWidth={1.5} /> : <ChevronLeft size={16} strokeWidth={1.5} />}
              onClick={() => setCollapsed(!collapsed)}
              style={{
                color: 'rgba(0, 0, 0, 0.65)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(0, 0, 0, 0.04)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            />
          </div>

          {/* 导航列表 */}
          <div style={navigationStyle}>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              const isHovered = hoveredItem === item.path;

              return (
                <Tooltip
                  key={item.path}
                  title={collapsed ? t(item.labelKey) : ''}
                  placement="right"
                >
                  <Link
                    to={item.path}
                    style={getNavItemStyle(isActive, isHovered)}
                    onMouseEnter={() => setHoveredItem(item.path)}
                    onMouseLeave={() => setHoveredItem(null)}
                    data-tour={item.tourId}
                  >
                    <Icon size={20} strokeWidth={1.5} />
                    {!collapsed && <span style={navLabelStyle}>{t(item.labelKey)}</span>}
                  </Link>
                </Tooltip>
              );
            })}
          </div>

          {/* Footer */}
          <div style={footerStyle}>
            <div style={footerDecorStyle} />

            {/* 用户头像下拉菜单 */}
            <UserMenu collapsed={collapsed} placement="topLeft" />

            <Tooltip title={t('pages.workspace.goToChat')}>
              <Button
                type="text"
                icon={<Home size={16} strokeWidth={1.5} />}
                onClick={() => navigate('/chat')}
                data-tour="workspace-home-button"
                style={{
                  color: 'rgba(0, 0, 0, 0.65)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(0, 0, 0, 0.04)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              />
            </Tooltip>
          </div>
        </div>

        {/* 主内容区域 */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minHeight: '100vh',
          overflow: 'hidden'
        }}
          data-tour="workspace-main-area"
        >
          <div style={{
            flex: 1,
            padding: '0',
            overflow: 'auto',
            height: '100%'
          }}>
            {children}
          </div>
        </div>


      </div>
    </>
  );
};

export default WorkspaceLayout;
