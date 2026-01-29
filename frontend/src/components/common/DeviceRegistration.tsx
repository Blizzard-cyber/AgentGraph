/**
 * 设备注册和认证UI组件
 * 用于显示设备的注册状态、自助注册表单、认证状态等
 */

import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Space, message as antMessage, Spin } from 'antd';
import { Smartphone, Lock, MapPin, Check } from 'lucide-react';
import { deviceService, DeviceCredentials, SystemInfo } from '../../services/deviceService';

interface DeviceRegistrationProps {
  onRegistrationSuccess?: (credentials: DeviceCredentials) => void;
  onAuthenticationSuccess?: (token: string) => void;
  mode?: 'register' | 'authenticate';
  compact?: boolean;
  currentStatus?: 'pending' | 'approved' | 'active' | 'disabled';
}

const DeviceRegistration: React.FC<DeviceRegistrationProps> = ({
  onRegistrationSuccess,
  onAuthenticationSuccess,
  mode = 'register',
  compact = false,
  currentStatus,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [systemInfoLoading, setSystemInfoLoading] = useState(true);
  const [currentMode, setCurrentMode] = useState<'register' | 'authenticate'>(mode);
  const [credentials, setCredentials] = useState<DeviceCredentials | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);

  useEffect(() => {
    const initializeForm = async () => {
      setSystemInfoLoading(true);
      try {
        // 获取系统信息
        const info = await deviceService.getSystemInfo();
        setSystemInfo(info);

        // 设置表单默认值
        form.setFieldsValue({
          deviceIdentifier: info.device_id_suggestion,
          deviceName: info.hostname,
          location: info.default_location,
          // 使用白名单中的有效 PSK（需替换为实际的有效 PSK）
          psk: 'dev_sec_5UZTvYvZje6cbwR1GSWDSRgrir-Y7DPIgOT6biKD5DA'
        });
      } catch (error) {
        console.error('Failed to initialize form:', error);
      } finally {
        setSystemInfoLoading(false);
      }

      // 加载已保存的凭证
      const savedCredentials = deviceService.getCredentials();
      setCredentials(savedCredentials);
      if (savedCredentials && mode === 'authenticate') {
        setCurrentMode('authenticate');
      }
    };

    initializeForm();
  }, [form, mode]);

  const handleRegisterSubmit = async (values: any) => {
    setLoading(true);
    try {
      const result = await deviceService.selfRegisterDevice(
        values.deviceIdentifier,
        values.psk,
        values.deviceName,
        values.location || undefined
      );

      if (result.success) {
        setCredentials(result.credentials || null);
        antMessage.success('设备注册成功！请等待管理员审批。');
        if (result.credentials) {
          onRegistrationSuccess?.(result.credentials);
        }
        form.resetFields();
        setCurrentMode('authenticate');
      }
    } catch (error: any) {
      antMessage.error(error.message || '设备注册失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAuthenticateSubmit = async (values: any) => {
    if (!credentials) {
      antMessage.error('请先注册设备');
      return;
    }

    setLoading(true);
    try {
      const response = await deviceService.authenticateDevice(
        credentials.device_id,
        credentials.device_secret
      );

      antMessage.success('设备认证成功！');
      if (response.success && response.access_token) {
        onAuthenticationSuccess?.(response.access_token);
      }
      form.resetFields();
    } catch (error: any) {
      antMessage.error(error.message || '设备认证失败');
    } finally {
      setLoading(false);
    }
  };

  const onFinish = (values: any) => {
    if (currentMode === 'register') {
      handleRegisterSubmit(values);
    } else {
      handleAuthenticateSubmit(values);
    }
  };

  const containerStyle = compact ? {
    padding: '12px'
  } : {
    padding: '0'
  };

  if (systemInfoLoading) {
    return (
      <div style={{ ...containerStyle, textAlign: 'center', padding: '20px' }}>
        <Spin size="small" />
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <Spin spinning={loading}>
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          autoComplete="off"
        >
          {currentMode === 'register' ? (
            <>
              <Form.Item
                label={
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 500 }}>
                    <Smartphone size={16} />
                    设备标识符
                  </span>
                }
                name="deviceIdentifier"
                rules={[
                  { required: true, message: '请输入设备标识符' },
                  { min: 3, message: '设备标识符至少3个字符' }
                ]}
                extra={<span style={{ fontSize: '11px', color: '#999' }}>默认值：本机MAC地址</span>}
              >
                <Input
                  placeholder="例如: MAC-00:1A:44:11:3A:B7"
                  style={{
                    borderRadius: '6px',
                    fontSize: '13px',
                    padding: '8px 12px',
                    height: '36px'
                  }}
                />
              </Form.Item>

              <Form.Item
                label={
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 500 }}>
                    <Lock size={16} />
                    预共享密钥 (PSK)
                  </span>
                }
                name="psk"
                rules={[
                  { required: true, message: '请输入PSK' },
                  { min: 32, message: 'PSK 长度至少为 32 字符' }
                ]}
                extra={<span style={{ fontSize: '11px', color: '#999' }}>由云端发放或出厂预置，需在白名单中（dev_sec_/psk_ 开头，≥32字符）</span>}
              >
                <Input.Password
                  placeholder="输入出厂预置的密钥"
                  style={{
                    borderRadius: '6px',
                    fontSize: '13px',
                    padding: '8px 12px',
                    height: '36px'
                  }}
                />
              </Form.Item>

              <Form.Item
                label={
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 500 }}>
                    <Smartphone size={16} />
                    设备名称
                  </span>
                }
                name="deviceName"
                rules={[{ required: true, message: '请输入设备名称' }]}
                extra={<span style={{ fontSize: '11px', color: '#999' }}>默认值：本机hostname</span>}
              >
                <Input
                  placeholder="例如: MAG Edge Device 001"
                  style={{
                    borderRadius: '6px',
                    fontSize: '13px',
                    padding: '8px 12px',
                    height: '36px'
                  }}
                />
              </Form.Item>

              <Form.Item
                label={
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 500 }}>
                    <MapPin size={16} />
                    位置
                  </span>
                }
                name="location"
                rules={[{ required: true, message: '请输入位置信息' }]}
                extra={<span style={{ fontSize: '11px', color: '#999' }}>默认值：成都</span>}
              >
                <Input
                  placeholder="例如: Beijing Data Center"
                  style={{
                    borderRadius: '6px',
                    fontSize: '13px',
                    padding: '8px 12px',
                    height: '36px'
                  }}
                />
              </Form.Item>
            </>
          ) : (
            <div style={{
              padding: '12px 16px',
              background: 'rgba(24, 144, 255, 0.08)',
              borderRadius: '6px',
              marginBottom: '16px',
              fontSize: '13px',
              color: 'rgba(0, 0, 0, 0.65)',
              lineHeight: 1.6
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <Check size={16} color="#1890ff" />
                <strong style={{ color: '#2d2d2d' }}>设备信息</strong>
              </div>
              <div>设备ID: <code style={{ fontSize: '11px', background: 'rgba(0,0,0,0.05)', padding: '2px 4px', borderRadius: '3px' }}>{credentials?.device_id}</code></div>
              <div style={{ marginTop: '4px' }}>状态: <strong>{(currentStatus || credentials?.status) === 'active' ? '✅ 已激活' : (currentStatus || credentials?.status) === 'approved' ? ' 待提交认证' : '待批准'}</strong></div>
            </div>
          )}

          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{
                borderRadius: '6px',
                height: '40px',
                fontSize: '14px',
                fontWeight: 500,
                letterSpacing: '0.3px',
                background: 'linear-gradient(135deg, #1890ff 0%, #40a9ff 100%)',
                border: 'none',
                boxShadow: '0 2px 6px rgba(24, 144, 255, 0.25)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px'
              }}
            >
              {currentMode === 'register' ? '📝 提交注册' : '🔐 提交认证'}
            </Button>
          </Form.Item>

          {credentials && currentMode === 'register' && (
            <Button
              type="link"
              onClick={() => setCurrentMode('authenticate')}
              style={{ marginTop: '12px', fontSize: '13px', display: 'block', width: '100%', textAlign: 'center' }}
            >
              已获批准？点击进行认证
            </Button>
          )}
        </Form>
      </Spin>
    </div>
  );
};

export default DeviceRegistration;
