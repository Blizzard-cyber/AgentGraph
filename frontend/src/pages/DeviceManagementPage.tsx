/**
 * 设备管理页面
 * 展示设备信息、云端连接状态，以及自动配置的设备状态
 */

import React, { useState, useEffect } from 'react';
import { Layout, Card, Row, Col, Typography, Button, Space, Tag as AntTag, Spin, Tooltip, App, Divider, Badge, Statistic, Modal } from 'antd';
import { Smartphone, Cloud, Check, X, AlertCircle, RefreshCw, Settings } from 'lucide-react';
import { deviceService, DeviceCredentials } from '../services/deviceService';
import DeviceRegistration from '../components/common/DeviceRegistration';
import { useT } from '../i18n/hooks';
import './DeviceManagementPage.css';

const { Header, Content } = Layout;
const { Text, Title } = Typography;

interface DeviceStatus {
  state: 'pending' | 'approved' | 'active' | 'disabled' | null;
  lastUpdate?: number;
  cloudConnected?: boolean;
  registrationTime?: number;
}

const DeviceManagementPage: React.FC = () => {
  const t = useT();
  const { message } = App.useApp();
  const [credentials, setCredentials] = useState<DeviceCredentials | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatus>({ state: null });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [setupModalVisible, setSetupModalVisible] = useState(false);
  const [autoConfigured, setAutoConfigured] = useState(true);
  const [showAuthSection, setShowAuthSection] = useState(false);

  useEffect(() => {
    loadDeviceInfo();
    // 每5秒检查云端连接状态
    const checkInterval = setInterval(() => checkCloudConnection(), 5000);
    // 每10秒同步一次设备状态（查询审批状态）
    const syncInterval = setInterval(() => syncDeviceStatus(), 10000);
    // 每30秒向云端发送一次心跳
    const heartbeatInterval = setInterval(() => sendHeartbeat(), 30000);
    return () => {
      clearInterval(checkInterval);
      clearInterval(syncInterval);
      clearInterval(heartbeatInterval);
    };
  }, []);

  // 监听设备状态变化，当变为approved时自动显示认证界面
  useEffect(() => {
    if (deviceStatus.state === 'approved' && !token) {
      setShowAuthSection(true);
    }
  }, [deviceStatus.state, token]);

  const loadDeviceInfo = async () => {
    setLoading(true);
    try {
      const savedCredentials = deviceService.getCredentials();
      const savedToken = deviceService.getDeviceToken();

      setCredentials(savedCredentials);
      setToken(savedToken);

      // 获取设备状态（从后端获取最新状态）
      if (savedCredentials) {
        const mockStatus: DeviceStatus = {
          state: savedToken ? 'active' : savedCredentials.device_id ? 'approved' : 'pending',
          lastUpdate: Date.now(),
          cloudConnected: !!savedToken,
          registrationTime: savedCredentials.device_id ? Date.now() - 3600000 : undefined
        };
        setDeviceStatus(mockStatus);
        
        // 立即同步一次状态
        await syncDeviceStatus();
      } else {
        setAutoConfigured(false);
        setDeviceStatus({ state: null });
      }
    } catch (error) {
      console.error('Failed to load device info:', error);
      message.error('设备信息加载失败');
    } finally {
      setLoading(false);
    }
  };

  const syncDeviceStatus = async () => {
    if (!credentials?.device_id) return;
    
    try {
      const response = await fetch('/api/device/sync-status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: credentials.device_id,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        console.log('设备状态同步:', data);
        
        if (data.success && data.status) {
          // 更新设备状态
          const statusMap: Record<string, any> = {
            'pending': 'pending',
            'approved': 'approved',
            'active': 'active',
            'disabled': 'disabled'
          };
          
          setDeviceStatus(prev => ({
            ...prev,
            state: statusMap[data.status] || 'pending',
            lastUpdate: Date.now()
          }));
          
          // 如果状态更新，显示提示
          if (data.updated) {
            message.info(`设备状态已更新为: ${data.status}`);
          }
        }
      } else {
        console.error('状态同步失败:', response.status);
      }
    } catch (error) {
      console.error('Failed to sync device status:', error);
    }
  };

  const sendHeartbeat = async () => {
    if (!credentials?.device_id) return;
    
    try {
      const response = await fetch('/api/device/heartbeat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: credentials.device_id,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        console.log('心跳发送成功:', data);
        if (data.success) {
          setDeviceStatus(prev => ({
            ...prev,
            cloudConnected: true,
            lastUpdate: Date.now()
          }));
        }
      } else {
        console.error('心跳发送失败:', response.status);
      }
    } catch (error) {
      console.error('Failed to send heartbeat:', error);
    }
  };

  const checkCloudConnection = async () => {
    if (!credentials) return;
    
    try {
      // 实际应该调用后端API检查连接
      const isConnected = !!token;
      setDeviceStatus(prev => ({
        ...prev,
        cloudConnected: isConnected,
        lastUpdate: Date.now()
      }));
    } catch (error) {
      console.error('Failed to check cloud connection:', error);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadDeviceInfo();
      await checkCloudConnection();
      message.success('设备信息已刷新');
    } catch (error) {
      message.error('刷新失败');
    } finally {
      setRefreshing(false);
    }
  };

  const handleRegistrationSuccess = (creds: DeviceCredentials) => {
    setCredentials(creds);
    setAutoConfigured(true);
    setDeviceStatus(prev => ({
      ...prev,
      state: 'pending',
      registrationTime: Date.now()
    }));
    message.success('设备注册成功，请等待云端审批');
  };

  const handleAuthenticationSuccess = (accessToken: string) => {
    setToken(accessToken);
    setDeviceStatus(prev => ({
      ...prev,
      state: 'active',
      cloudConnected: true,
      lastUpdate: Date.now()
    }));
    message.success('设备认证成功，已与云端连接');
  };

  const getStatusColor = (state: DeviceStatus['state']) => {
    switch (state) {
      case 'active':
        return 'success';
      case 'approved':
        return 'processing';
      case 'pending':
        return 'warning';
      case 'disabled':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusText = (state: DeviceStatus['state']) => {
    switch (state) {
      case 'active':
        return '已激活';
      case 'approved':
        return '已批准';
      case 'pending':
        return '待批准';
      case 'disabled':
        return '已禁用';
      default:
        return '未注册';
    }
  };

  const renderStatusBadge = (state: DeviceStatus['state'], connected?: boolean) => {
    if (!state) {
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertCircle size={16} color="#faad14" />
          <Text type="warning">未注册</Text>
        </div>
      );
    }

    const statusColor = getStatusColor(state);
    const isActive = state === 'active' && connected;

    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <Badge status={isActive ? 'success' : 'processing'} />
        <AntTag color={statusColor}>{getStatusText(state)}</AntTag>
        {connected && <Check size={16} color="#52c41a" />}
      </div>
    );
  };

  if (loading) {
    return (
      <Layout style={{ height: '100%', minHeight: 0, background: '#ffffff', display: 'flex', flexDirection: 'column' }}>
        <Content style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
          <Spin size="large" tip="加载设备信息中..." />
        </Content>
      </Layout>
    );
  }

  return (
    <Layout style={{ height: '100%', minHeight: 0, background: '#ffffff', display: 'flex', flexDirection: 'column' }}>
      {/* Header 顶栏 */}
      <Header style={{
        background: 'linear-gradient(to bottom, rgba(255, 255, 255, 0.8), rgba(230, 244, 255, 0.6))',
        backdropFilter: 'blur(20px)',
        padding: '0 32px',
        borderBottom: 'none',
        boxShadow: '0 2px 8px rgba(24, 144, 255, 0.08)',
        position: 'relative'
      }}>
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: '20%',
          right: '20%',
          height: '1px',
          background: 'linear-gradient(to right, transparent, rgba(24, 144, 255, 0.3) 50%, transparent)'
        }} />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '100%' }}>
          <Space size="large">
            <Smartphone size={28} color="#1890ff" strokeWidth={1.5} />
            <Title level={4} style={{
              margin: 0,
              color: '#2d2d2d',
              fontWeight: 500,
              letterSpacing: '2px',
              fontSize: '18px'
            }}>
              {t('pages.workspace.deviceManagement')}
            </Title>
            {credentials && (
              <AntTag style={{
                background: 'rgba(24, 144, 255, 0.08)',
                color: '#1890ff',
                border: '1px solid rgba(24, 144, 255, 0.25)',
                borderRadius: '6px',
                fontWeight: 500,
                padding: '4px 12px',
                fontSize: '12px'
              }}>
                {credentials.device_name || '设备已注册'}
              </AntTag>
            )}
          </Space>

          <Space size={12}>
            <Button
              icon={<RefreshCw size={16} strokeWidth={1.5} />}
              loading={refreshing}
              onClick={handleRefresh}
              style={{
                borderRadius: '6px',
                border: '1px solid rgba(24, 144, 255, 0.2)',
                background: 'rgba(255, 255, 255, 0.85)',
                color: 'rgba(0, 0, 0, 0.65)',
                fontWeight: 500,
                fontSize: '14px',
                letterSpacing: '0.3px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '0 16px'
              }}
            >
              刷新
            </Button>
            {autoConfigured && credentials && (
              <Button
                icon={<Settings size={16} strokeWidth={1.5} />}
                onClick={() => setSetupModalVisible(true)}
                style={{
                  borderRadius: '6px',
                  border: '1px solid rgba(24, 144, 255, 0.2)',
                  background: 'rgba(255, 255, 255, 0.85)',
                  color: 'rgba(0, 0, 0, 0.65)',
                  fontWeight: 500,
                  fontSize: '14px',
                  letterSpacing: '0.3px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '0 16px'
                }}
              >
                高级配置
              </Button>
            )}
          </Space>
        </div>
      </Header>

      {/* Content 内容区 */}
      <Content style={{ flex: 1, minHeight: 0, padding: '24px 48px 32px', overflow: 'auto', display: 'flex', justifyContent: 'center' }}>
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {!credentials ? (
            // 未配置状态：显示注册表单
            <Row gutter={[32, 32]}>
              <Col xs={24} md={12}>
                <Card
                  style={{
                    borderRadius: '12px',
                    border: '1px solid rgba(24, 144, 255, 0.15)',
                    boxShadow: '0 1px 4px rgba(24, 144, 255, 0.08)'
                  }}
                >
                  <Space direction="vertical" style={{ width: '100%' }} size="large">
                    <div>
                      <Title level={5} style={{ margin: 0, color: '#2d2d2d' }}>
                        🚀 设备配置
                      </Title>
                      <Text type="secondary" style={{ fontSize: '13px', marginTop: '4px', display: 'block' }}>
                        首次启动时进行自动配置。系统将向云端注册此设备并建立连接。
                      </Text>
                    </div>
                    <DeviceRegistration
                      onRegistrationSuccess={handleRegistrationSuccess}
                      onAuthenticationSuccess={handleAuthenticationSuccess}
                    />
                  </Space>
                </Card>
              </Col>

              <Col xs={24} md={12}>
                <Card
                  style={{
                    borderRadius: '12px',
                    border: '1px solid rgba(24, 144, 255, 0.15)',
                    boxShadow: '0 1px 4px rgba(24, 144, 255, 0.08)',
                    background: 'linear-gradient(135deg, rgba(24, 144, 255, 0.03) 0%, rgba(24, 144, 255, 0.01) 100%)'
                  }}
                >
                  <Space direction="vertical" style={{ width: '100%' }} size="large">
                    <div>
                      <Title level={5} style={{ margin: 0, color: '#2d2d2d' }}>
                        ℹ️ 配置信息
                      </Title>
                    </div>

                    <div style={{
                      padding: '12px 16px',
                      background: 'rgba(24, 144, 255, 0.08)',
                      borderLeft: '3px solid #1890ff',
                      borderRadius: '4px'
                    }}>
                      <Text strong style={{ fontSize: '13px', color: '#2d2d2d' }}>
                        自动配置说明
                      </Text>
                      <div style={{ fontSize: '12px', color: 'rgba(0, 0, 0, 0.65)', marginTop: '8px', lineHeight: 1.6 }}>
                        <p style={{ margin: '0 0 8px 0' }}>
                          ✓ 系统启动时自动扫描本地网络设备
                        </p>
                        <p style={{ margin: '0 0 8px 0' }}>
                          ✓ 自动生成设备标识符和密钥
                        </p>
                        <p style={{ margin: '0 0 8px 0' }}>
                          ✓ 自动向云端注册并同步状态
                        </p>
                        <p style={{ margin: '0 0 8px 0' }}>
                          ✓ 一旦获得云端批准，自动激活连接
                        </p>
                        <p style={{ margin: 0 }}>
                          ✓ 后续更新自动同步，无需人工干预
                        </p>
                      </div>
                    </div>

                    <Divider style={{ margin: '16px 0' }} />

                    <div>
                      <Text strong style={{ fontSize: '13px', color: '#2d2d2d' }}>
                        需要帮助？
                      </Text>
                      <div style={{ fontSize: '12px', color: 'rgba(0, 0, 0, 0.65)', marginTop: '8px', lineHeight: 1.8 }}>
                        <p><strong>PSK：</strong>预共享密钥，出厂时预置</p>
                        <p><strong>设备ID：</strong>MAC地址或UUID</p>
                        <p><strong>认证：</strong>通过后自动建立连接</p>
                      </div>
                    </div>
                  </Space>
                </Card>
              </Col>
            </Row>
          ) : (
            // 已配置状态：显示设备信息和连接状态
            <Space direction="vertical" style={{ width: '100%' }} size="large">
            {/* 顶部状态卡片 - 简化版本 */}
            <Card style={{
              borderRadius: '12px',
              border: 'none',
              background: deviceStatus.state === 'active' 
                ? 'linear-gradient(135deg, rgba(52, 211, 153, 0.05) 0%, rgba(52, 211, 153, 0.02) 100%)'
                : deviceStatus.state === 'approved'
                ? 'linear-gradient(135deg, rgba(24, 144, 255, 0.05) 0%, rgba(24, 144, 255, 0.02) 100%)'
                : 'linear-gradient(135deg, rgba(250, 173, 20, 0.05) 0%, rgba(250, 173, 20, 0.02) 100%)',
              boxShadow: '0 1px 2px rgba(0, 0, 0, 0.06)',
              padding: '16px'
            }}>
              <Row gutter={[24, 0]}>
                <Col xs={24} sm={12} lg={6}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '50%',
                      background: deviceStatus.state === 'active' ? 'rgba(52, 211, 153, 0.15)' : 'rgba(24, 144, 255, 0.15)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '24px'
                    }}>
                      {deviceStatus.state === 'active' ? '✅' : deviceStatus.state === 'pending' ? '⏳' : '📱'}
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: '12px' }}>设备状态</Text>
                      <div style={{ fontSize: '16px', fontWeight: 600, color: deviceStatus.state === 'active' ? '#22c55e' : '#1890ff', marginTop: '2px' }}>
                        {getStatusText(deviceStatus.state)}
                      </div>
                    </div>
                  </div>
                </Col>

                <Col xs={24} sm={12} lg={6}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '50%',
                      background: deviceStatus.cloudConnected ? 'rgba(52, 211, 153, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '24px'
                    }}>
                      {deviceStatus.cloudConnected ? '☁️' : '❌'}
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: '12px' }}>云端连接</Text>
                      <div style={{ fontSize: '16px', fontWeight: 600, color: deviceStatus.cloudConnected ? '#22c55e' : '#ef4444', marginTop: '2px' }}>
                        {deviceStatus.cloudConnected ? '已连接' : '未连接'}
                      </div>
                    </div>
                  </div>
                </Col>

                <Col xs={24} sm={12} lg={6}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '50%',
                      background: token ? 'rgba(52, 211, 153, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '24px'
                    }}>
                      {token ? '🔐' : '🔓'}
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: '12px' }}>认证</Text>
                      <div style={{ fontSize: '16px', fontWeight: 600, color: token ? '#22c55e' : '#ef4444', marginTop: '2px' }}>
                        {token ? '已认证' : '未认证'}
                      </div>
                    </div>
                  </div>
                </Col>

                <Col xs={24} sm={12} lg={6}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '50%',
                      background: 'rgba(99, 102, 241, 0.1)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '20px'
                    }}>
                      🕐
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: '12px' }}>更新时间</Text>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: '#595959', marginTop: '2px' }}>
                        {deviceStatus.lastUpdate ? new Date(deviceStatus.lastUpdate).toLocaleTimeString() : '—'}
                      </div>
                    </div>
                  </div>
                </Col>
              </Row>
            </Card>

            {/* 状态流程进度卡片 - 增强版本 */}
            <Card style={{
              borderRadius: '12px',
              border: 'none',
              background: 'linear-gradient(135deg, rgba(24, 144, 255, 0.03) 0%, rgba(24, 144, 255, 0.01) 100%)',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)'
            }}>
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text strong style={{ fontSize: '14px', color: '#2d2d2d' }}>
                    🔄 注册认证流程
                  </Text>
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    {deviceStatus.state === 'pending' && '⏳ 等待管理员审批'}
                    {deviceStatus.state === 'approved' && '⏳ 待提交认证'}
                    {deviceStatus.state === 'active' && '✅ 已完成'}
                  </Text>
                </div>

                {/* 流程步骤 - 增强动画效果 */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '12px', gap: '8px' }}>
                  {/* 第一步：注册 */}
                  <div style={{ textAlign: 'center', flex: 1 }}>
                    <div style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '50%',
                      background: 'rgba(24, 144, 255, 0.9)',
                      color: 'white',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '0 auto 8px',
                      fontSize: '18px',
                      fontWeight: 'bold',
                      boxShadow: '0 2px 8px rgba(24, 144, 255, 0.3)',
                      transition: 'all 0.3s ease'
                    }}>
                      ✓
                    </div>
                    <Text style={{ fontSize: '12px', color: '#2d2d2d', fontWeight: 600 }}>注册</Text>
                    <div style={{ fontSize: '11px', color: '#52c41a', marginTop: '2px' }}>已完成</div>
                  </div>

                  {/* 箭头1 */}
                  <div style={{
                    flex: 0.5,
                    textAlign: 'center',
                    color: 'rgba(24, 144, 255, 0.6)',
                    fontSize: '20px',
                    animation: 'pulse 2s infinite'
                  }}>
                    →
                  </div>

                  {/* 第二步：审批 */}
                  <div style={{ textAlign: 'center', flex: 1 }}>
                    <div style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '50%',
                      background: deviceStatus.state === 'pending' ? 'rgba(250, 173, 20, 0.2)' : 'rgba(24, 144, 255, 0.9)',
                      color: deviceStatus.state === 'pending' ? '#faad14' : 'white',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '0 auto 8px',
                      fontSize: '18px',
                      fontWeight: 'bold',
                      border: deviceStatus.state === 'pending' ? '2px solid #faad14' : 'none',
                      boxShadow: deviceStatus.state === 'pending' ? '0 2px 8px rgba(250, 173, 20, 0.3)' : '0 2px 8px rgba(24, 144, 255, 0.3)',
                      animation: deviceStatus.state === 'pending' ? 'pulse 1s infinite' : 'none',
                      transition: 'all 0.3s ease'
                    }}>
                      {deviceStatus.state === 'pending' ? '⏳' : '✓'}
                    </div>
                    <Text style={{ fontSize: '12px', color: '#2d2d2d', fontWeight: 600 }}>审批</Text>
                    <div style={{ fontSize: '11px', color: deviceStatus.state === 'pending' ? '#faad14' : '#52c41a', marginTop: '2px' }}>
                      {deviceStatus.state === 'pending' ? '进行中' : '已完成'}
                    </div>
                  </div>

                  {/* 箭头2 */}
                  <div style={{
                    flex: 0.5,
                    textAlign: 'center',
                    color: deviceStatus.state === 'approved' || deviceStatus.state === 'active' ? 'rgba(24, 144, 255, 0.6)' : 'rgba(0, 0, 0, 0.15)',
                    fontSize: '20px',
                    animation: deviceStatus.state === 'approved' ? 'pulse 1.5s infinite' : 'none'
                  }}>
                    →
                  </div>

                  {/* 第三步：认证 */}
                  <div style={{ textAlign: 'center', flex: 1 }}>
                    <div style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '50%',
                      background: 
                        deviceStatus.state === 'active' ? 'rgba(52, 211, 153, 0.9)' :
                        deviceStatus.state === 'approved' ? 'rgba(24, 144, 255, 0.2)' :
                        'rgba(0, 0, 0, 0.08)',
                      color: 
                        deviceStatus.state === 'active' ? 'white' :
                        deviceStatus.state === 'approved' ? '#1890ff' :
                        '#bfbfbf',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '0 auto 8px',
                      fontSize: '18px',
                      fontWeight: 'bold',
                      border: deviceStatus.state === 'approved' ? '2px solid #1890ff' : 'none',
                      boxShadow: deviceStatus.state === 'approved' ? '0 2px 8px rgba(24, 144, 255, 0.2)' : 'none',
                      animation: deviceStatus.state === 'approved' ? 'pulse 1.5s infinite' : 'none',
                      transition: 'all 0.3s ease'
                    }}>
                      {deviceStatus.state === 'active' ? '✓' : deviceStatus.state === 'approved' ? '○' : '○'}
                    </div>
                    <Text style={{ fontSize: '12px', color: '#2d2d2d', fontWeight: 600 }}>认证</Text>
                    <div style={{ fontSize: '11px', color: deviceStatus.state === 'approved' ? '#1890ff' : deviceStatus.state === 'active' ? '#52c41a' : '#bfbfbf', marginTop: '2px' }}>
                      {deviceStatus.state === 'active' ? '已完成' : deviceStatus.state === 'approved' ? '进行中' : '待进行'}
                    </div>
                  </div>
                </div>
              </Space>
            </Card>

            {/* 设备信息卡片 - 精简版本 */}
            <Card style={{
              borderRadius: '12px',
              border: 'none',
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.02) 0%, rgba(99, 102, 241, 0.01) 100%)',
              boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'
            }}>
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <Title level={5} style={{ margin: 0, color: '#2d2d2d' }}>
                  📋 设备信息
                </Title>

                <Row gutter={[24, 16]}>
                  <Col xs={24} md={12}>
                    <div>
                      <Text type="secondary" style={{ fontSize: '12px' }}>设备ID</Text>
                      <div style={{
                        marginTop: '6px',
                        padding: '10px 12px',
                        background: 'rgba(99, 102, 241, 0.05)',
                        borderRadius: '6px',
                        fontFamily: 'monospace',
                        fontSize: '12px',
                        wordBreak: 'break-all',
                        color: '#2d2d2d'
                      }}>
                        {credentials.device_id}
                      </div>
                    </div>
                  </Col>

                  <Col xs={24} md={12}>
                    <div>
                      <Text type="secondary" style={{ fontSize: '12px' }}>设备名称</Text>
                      <div style={{
                        marginTop: '6px',
                        padding: '10px 12px',
                        background: 'rgba(99, 102, 241, 0.05)',
                        borderRadius: '6px',
                        color: '#2d2d2d'
                      }}>
                        {credentials.device_name || '—'}
                      </div>
                    </div>
                  </Col>

                  <Col xs={24} md={12}>
                    <div>
                      <Text type="secondary" style={{ fontSize: '12px' }}>位置</Text>
                      <div style={{
                        marginTop: '6px',
                        padding: '10px 12px',
                        background: 'rgba(99, 102, 241, 0.05)',
                        borderRadius: '6px',
                        color: '#2d2d2d'
                      }}>
                        {credentials.location || '—'}
                      </div>
                    </div>
                  </Col>

                  <Col xs={24} md={12}>
                    <div>
                      <Text type="secondary" style={{ fontSize: '12px' }}>状态</Text>
                      <div style={{
                        marginTop: '6px',
                        padding: '10px 12px',
                        background: deviceStatus.state === 'active' ? 'rgba(52, 211, 153, 0.1)' : 'rgba(24, 144, 255, 0.1)',
                        borderRadius: '6px',
                        color: deviceStatus.state === 'active' ? '#22c55e' : '#1890ff',
                        fontWeight: 600,
                        fontSize: '12px'
                      }}>
                        {deviceStatus.state === 'pending' && '⏳ 待批准'}
                        {deviceStatus.state === 'approved' && '⏳ 待提交认证'}
                        {deviceStatus.state === 'active' && '✅ 已激活'}
                        {deviceStatus.state === 'disabled' && '❌ 已禁用'}
                      </div>
                    </div>
                  </Col>
                </Row>
              </Space>
            </Card>

            {/* 认证状态卡片 */}
            {deviceStatus.state !== 'active' && (
              <Card style={{
                borderRadius: '12px',
                border: 'none',
                background: 'linear-gradient(135deg, rgba(24, 144, 255, 0.04) 0%, rgba(24, 144, 255, 0.02) 100%)',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
                transition: 'all 0.3s ease'
              }}>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <div style={{
                    padding: '12px 16px',
                    background: deviceStatus.state === 'approved' ? 'rgba(24, 144, 255, 0.08)' : 'rgba(250, 173, 20, 0.08)',
                    borderLeft: `3px solid ${deviceStatus.state === 'approved' ? '#1890ff' : '#faad14'}`,
                    borderRadius: '4px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <Text strong style={{ fontSize: '14px', color: '#2d2d2d' }}>
                          {deviceStatus.state === 'approved' ? '⏳ 待提交认证' : '⏳ 待认证'}
                        </Text>
                        <div style={{ fontSize: '12px', color: 'rgba(0, 0, 0, 0.65)', marginTop: '8px' }}>
                          {deviceStatus.state === 'pending'
                            ? '您的设备已注册，正在等待管理员批准。批准后请进行认证。'
                            : deviceStatus.state === 'approved'
                              ? '您的设备已获批准！请立即提交认证信息，建立与云端的安全连接。'
                              : '请先注册设备或等待审批。'}
                        </div>
                      </div>
                      {deviceStatus.state === 'approved' && !showAuthSection && (
                        <Button
                          type="primary"
                          size="small"
                          onClick={() => setShowAuthSection(!showAuthSection)}
                          style={{ fontSize: '12px' }}
                        >
                          {showAuthSection ? '收起' : '提交认证'}
                        </Button>
                      )}
                    </div>
                  </div>

                  {deviceStatus.state === 'approved' && !token && showAuthSection && (
                    <div style={{
                      padding: '16px',
                      background: 'rgba(255, 255, 255, 0.5)',
                      borderRadius: '8px',
                      border: '1px solid rgba(24, 144, 255, 0.2)',
                      animation: 'slideDown 0.3s ease'
                    }}>
                      <DeviceRegistration
                        mode="authenticate"
                        currentStatus={deviceStatus.state}
                        onRegistrationSuccess={handleRegistrationSuccess}
                        onAuthenticationSuccess={handleAuthenticationSuccess}
                        compact={true}
                      />
                    </div>
                  )}
                </Space>
              </Card>
            )}

            {/* 已激活状态 - 成功提示 */}
            {deviceStatus.state === 'active' && token && (
              <Card style={{
                borderRadius: '12px',
                border: 'none',
                background: 'linear-gradient(135deg, rgba(52, 211, 153, 0.04) 0%, rgba(52, 211, 153, 0.02) 100%)',
                boxShadow: '0 2px 8px rgba(52, 211, 153, 0.15)',
                animation: 'slideUp 0.5s ease'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{
                    width: '48px',
                    height: '48px',
                    borderRadius: '50%',
                    background: 'rgba(52, 211, 153, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '24px'
                  }}>
                    ✅
                  </div>
                  <div>
                    <Title level={5} style={{ margin: 0, color: '#22c55e', fontSize: '14px' }}>
                      设备已连接到云端
                    </Title>
                    <Text type="secondary" style={{ fontSize: '12px', display: 'block', marginTop: '4px' }}>
                      设备处于活跃状态，可以与云端正常通信。
                    </Text>
                  </div>
                </div>
              </Card>
            )}
          </Space>
          )}
        </div>
      </Content>

      {/* 高级配置弹窗 */}
      <Modal
        title="高级配置"
        open={setupModalVisible}
        onCancel={() => setSetupModalVisible(false)}
        footer={null}
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Card type="inner" title="当前配置">
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <div>
                <Text type="secondary">设备ID: </Text>
                <code>{credentials?.device_id}</code>
              </div>
              <div>
                <Text type="secondary">设备名称: </Text>
                <span>{credentials?.device_name}</span>
              </div>
              <div>
                <Text type="secondary">位置: </Text>
                <span>{credentials?.location}</span>
              </div>
            </Space>
          </Card>

          <Button
            type="primary"
            onClick={() => {
              if (credentials) {
                deviceService.clearCredentials();
                setCredentials(null);
                setToken(null);
                setDeviceStatus({ state: null });
                setAutoConfigured(false);
                setSetupModalVisible(false);
                message.success('设备配置已清除，请重新配置');
              }
            }}
            danger
          >
            清除配置并重新注册
          </Button>
        </Space>
      </Modal>
    </Layout>
  );
};

export default DeviceManagementPage;
