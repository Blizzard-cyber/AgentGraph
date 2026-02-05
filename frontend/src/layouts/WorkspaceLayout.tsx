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
  ChevronRight,
  Smartphone,
  Users
} from 'lucide-react';
import { useT } from '../i18n';
import UserMenu from '../components/common/UserMenu';
import { useTour, workspaceTourSteps } from '../components/tour';
import { getUserInfo } from '../utils/auth';
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
  
  // 获取用户信息用于权限判断
  const userInfo = getUserInfo();
  const isAdmin = userInfo?.role === 'admin' || userInfo?.role === 'super_admin';

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

  // 所有导航项
  const allNavItems = [
    { path: '/workspace/agent-manager', icon: Bot, labelKey: 'pages.workspace.agentManager', tourId: 'workspace-agent-manager', requiredRole: null },
    { path: '/workspace/graph-editor', icon: Network, labelKey: 'pages.workspace.graphEditor', tourId: 'workspace-graph-editor', requiredRole: null },
    { path: '/workspace/model-manager', icon: Cpu, labelKey: 'pages.workspace.modelManager', tourId: 'workspace-model-manager', requiredRole: null },
    { path: '/workspace/system-tools', icon: Wrench, labelKey: 'pages.workspace.systemTools', tourId: 'workspace-system-tools', requiredRole: null },
    { path: '/workspace/mcp-manager', icon: Plug, labelKey: 'pages.workspace.mcpManager', tourId: 'workspace-mcp-manager', requiredRole: null },
    { path: '/workspace/prompt-manager', icon: MessageSquareText, labelKey: 'pages.workspace.promptManager', tourId: 'workspace-prompt-manager', requiredRole: null },
    { path: '/workspace/file-manager', icon: FolderOpen, labelKey: 'pages.workspace.fileManager', tourId: 'workspace-file-manager', requiredRole: null },
    { path: '/workspace/memory-manager', icon: Database, labelKey: 'pages.workspace.memoryManager', tourId: 'workspace-memory-manager', requiredRole: null },
    { path: '/workspace/user-management', icon: Users, labelKey: 'pages.workspace.userManagement', tourId: 'workspace-user-management', requiredRole: 'admin' },
    { path: '/workspace/device-management', icon: Smartphone, labelKey: 'pages.workspace.deviceManagement', tourId: 'workspace-device-management', requiredRole: 'admin' },
  ];
  
  // 根据权限过滤导航项
  const navItems = allNavItems.filter(item => {
    if (item.requiredRole === null) return true;
    if (item.requiredRole === 'admin') return isAdmin;
    return false;
  });

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
    fontSize: '18px',
    fontWeight: 600,
    margin: 0,
    letterSpacing: '0.5px',
    opacity: collapsed ? 0 : 1,
    transition: 'opacity 0.3s ease',
    whiteSpace: 'normal',
    wordBreak: 'keep-all',
    lineHeight: '1.3',
    maxWidth: '240px'
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
          
          @keyframes titleGlow {
            0%, 100% { text-shadow: 0 0 8px rgba(24, 144, 255, 0.2); }
            50% { text-shadow: 0 0 12px rgba(24, 144, 255, 0.4); }
          }
          
          @keyframes subtleSlide {
            0% { transform: translateY(-2px); opacity: 0; }
            100% { transform: translateY(0); opacity: 1; }
          }
          
          .workspace-title {
            color: #1890ff;
            animation: titleGlow 3s ease-in-out infinite;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
          }
          
          .workspace-title-line:nth-child(1) {
            animation: subtleSlide 0.6s ease-out;
            color: #1890ff;
            display: block;
          }
          
          .workspace-title-line:nth-child(3) {
            animation: subtleSlide 0.6s ease-out 0.15s backwards;
            font-size: 0.9em;
            letter-spacing: 1px;
            color: #096dd9;
            display: block;
            text-align: center;
            margin-top: -4px;
          }
        `}
      </style>

      <div style={{ display: 'flex', height: '100vh', background: '#ffffff', overflow: 'hidden' }}>
        {/* 侧边栏 */}
        <div style={sidebarStyle} data-tour="workspace-sidebar">
          {/* Header */}
          <div style={headerStyle}>
            <div style={headerDecorStyle} />
            {!collapsed && (
              <h3 style={titleStyle} className="workspace-title">
                {t('pages.workspace.title').split('\n').map((line, idx) => (
                  <React.Fragment key={idx}>
                    <span className="workspace-title-line">{line}</span>
                    {idx === 0 && <br />}
                  </React.Fragment>
                ))}
              </h3>
            )}
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
          minHeight: 0,
          overflow: 'hidden'
        }}
          data-tour="workspace-main-area"
        >
          <div style={{
            flex: 1,
            padding: '0',
            overflow: 'auto',
            minHeight: 0
          }}>
            {children}
          </div>
        </div>


      </div>
    </>
  );
};

export default WorkspaceLayout;
