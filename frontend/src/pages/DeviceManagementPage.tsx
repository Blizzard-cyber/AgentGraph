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

  useEffect(() => {
    loadDeviceInfo();
    const interval = setInterval(() => checkCloudConnection(), 5000);
    return () => clearInterval(interval);
  }, []);

  const loadDeviceInfo = async () => {
    setLoading(true);
    try {
      const savedCredentials = deviceService.getCredentials();
      const savedToken = deviceService.getDeviceToken();

      setCredentials(savedCredentials);
      setToken(savedToken);

      // 模拟获取设备状态（实际应该从后端API获取）
      if (savedCredentials) {
        const mockStatus: DeviceStatus = {
          state: savedToken ? 'active' : savedCredentials.device_id ? 'approved' : 'pending',
          lastUpdate: Date.now(),
          cloudConnected: !!savedToken,
          registrationTime: savedCredentials.device_id ? Date.now() - 3600000 : undefined
        };
        setDeviceStatus(mockStatus);
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
      <Content style={{ flex: 1, minHeight: 0, padding: '24px 32px 32px', overflow: 'auto', display: 'flex', justifyContent: 'center' }}>
        <div style={{ width: '100%', maxWidth: '1200px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
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
            {/* 顶部状态卡片 */}
            <Row gutter={[16, 16]}>
              <Col xs={24} sm={12} lg={6}>
                <Card style={{ borderRadius: '12px', border: '1px solid rgba(24, 144, 255, 0.15)', textAlign: 'center' }}>
                  <Statistic
                    title="设备状态"
                    value={getStatusText(deviceStatus.state)}
                    valueStyle={{ color: getStatusColor(deviceStatus.state) === 'success' ? '#52c41a' : '#1890ff', fontSize: '16px' }}
                    prefix={
                      deviceStatus.state === 'active' ? <Check size={20} /> :
                      deviceStatus.state === 'pending' ? <AlertCircle size={20} /> : <Smartphone size={20} />
                    }
                  />
                </Card>
              </Col>

              <Col xs={24} sm={12} lg={6}>
                <Card style={{ borderRadius: '12px', border: '1px solid rgba(24, 144, 255, 0.15)', textAlign: 'center' }}>
                  <Statistic
                    title="云端连接"
                    value={deviceStatus.cloudConnected ? '已连接' : '未连接'}
                    valueStyle={{ color: deviceStatus.cloudConnected ? '#52c41a' : '#d4380d', fontSize: '16px' }}
                    prefix={deviceStatus.cloudConnected ? <Cloud size={20} color="#52c41a" /> : <Cloud size={20} color="#d4380d" />}
                  />
                </Card>
              </Col>

              <Col xs={24} sm={12} lg={6}>
                <Card style={{ borderRadius: '12px', border: '1px solid rgba(24, 144, 255, 0.15)', textAlign: 'center' }}>
                  <Statistic
                    title="认证状态"
                    value={token ? '已认证' : '未认证'}
                    valueStyle={{ color: token ? '#52c41a' : '#d4380d', fontSize: '16px' }}
                    prefix={token ? <Check size={20} /> : <X size={20} />}
                  />
                </Card>
              </Col>

              <Col xs={24} sm={12} lg={6}>
                <Card style={{ borderRadius: '12px', border: '1px solid rgba(24, 144, 255, 0.15)', textAlign: 'center' }}>
                  <Statistic
                    title="最后更新"
                    value={deviceStatus.lastUpdate ? new Date(deviceStatus.lastUpdate).toLocaleTimeString() : '—'}
                    valueStyle={{ fontSize: '14px', color: '#2d2d2d' }}
                  />
                </Card>
              </Col>
            </Row>

            {/* 设备详细信息 */}
            <Card style={{
              borderRadius: '12px',
              border: '1px solid rgba(24, 144, 255, 0.15)',
              boxShadow: '0 1px 4px rgba(24, 144, 255, 0.08)'
            }}>
              <Space direction="vertical" style={{ width: '100%' }} size="large">
                <Title level={5} style={{ margin: 0, color: '#2d2d2d' }}>
                  📋 设备信息
                </Title>

                <Row gutter={[32, 24]}>
                  <Col xs={24} md={12}>
                    <div style={{ fontSize: '13px' }}>
                      <Text type="secondary">设备ID</Text>
                      <div style={{
                        marginTop: '8px',
                        padding: '12px',
                        background: 'rgba(0, 0, 0, 0.02)',
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
                    <div style={{ fontSize: '13px' }}>
                      <Text type="secondary">设备名称</Text>
                      <div style={{
                        marginTop: '8px',
                        padding: '12px',
                        background: 'rgba(0, 0, 0, 0.02)',
                        borderRadius: '6px',
                        color: '#2d2d2d'
                      }}>
                        {credentials.device_name || '—'}
                      </div>
                    </div>
                  </Col>

                  <Col xs={24} md={12}>
                    <div style={{ fontSize: '13px' }}>
                      <Text type="secondary">位置</Text>
                      <div style={{
                        marginTop: '8px',
                        padding: '12px',
                        background: 'rgba(0, 0, 0, 0.02)',
                        borderRadius: '6px',
                        color: '#2d2d2d'
                      }}>
                        {credentials.location || '—'}
                      </div>
                    </div>
                  </Col>

                  <Col xs={24} md={12}>
                    <div style={{ fontSize: '13px' }}>
                      <Text type="secondary">注册时间</Text>
                      <div style={{
                        marginTop: '8px',
                        padding: '12px',
                        background: 'rgba(0, 0, 0, 0.02)',
                        borderRadius: '6px',
                        color: '#2d2d2d'
                      }}>
                        {deviceStatus.registrationTime ? new Date(deviceStatus.registrationTime).toLocaleString() : '—'}
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
                border: '1px solid rgba(24, 144, 255, 0.15)',
                background: 'linear-gradient(135deg, rgba(24, 144, 255, 0.03) 0%, rgba(24, 144, 255, 0.01) 100%)',
                boxShadow: '0 1px 4px rgba(24, 144, 255, 0.08)'
              }}>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <div style={{
                    padding: '12px 16px',
                    background: 'rgba(250, 173, 20, 0.08)',
                    borderLeft: '3px solid #faad14',
                    borderRadius: '4px'
                  }}>
                    <Text strong style={{ fontSize: '13px', color: '#2d2d2d' }}>
                      ⏳ 设备认证
                    </Text>
                    <div style={{ fontSize: '12px', color: 'rgba(0, 0, 0, 0.65)', marginTop: '8px' }}>
                      {deviceStatus.state === 'pending'
                        ? '您的设备已注册，正在等待管理员批准。批准后将自动进行认证。'
                        : '您的设备已获批准。请点击下方按钮进行认证，建立与云端的安全连接。'}
                    </div>
                  </div>

                  {deviceStatus.state === 'approved' && !token && (
                    <DeviceRegistration
                      onRegistrationSuccess={handleRegistrationSuccess}
                      onAuthenticationSuccess={handleAuthenticationSuccess}
                    />
                  )}
                </Space>
              </Card>
            )}

            {/* 已激活状态 */}
            {deviceStatus.state === 'active' && token && (
              <Card style={{
                borderRadius: '12px',
                border: '1px solid rgba(82, 196, 26, 0.15)',
                background: 'linear-gradient(135deg, rgba(82, 196, 26, 0.03) 0%, rgba(82, 196, 26, 0.01) 100%)',
                boxShadow: '0 1px 4px rgba(82, 196, 26, 0.08)'
              }}>
                <Space direction="vertical" style={{ width: '100%' }} size="small">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Check size={20} color="#52c41a" />
                    <Title level={5} style={{ margin: 0, color: '#52c41a' }}>
                      设备已成功连接到云端
                    </Title>
                  </div>
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    设备处于活跃状态，可以与云端正常通信。系统将自动同步更新和维护连接状态。
                  </Text>
                </Space>
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
