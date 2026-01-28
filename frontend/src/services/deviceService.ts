/**
 * 设备注册和认证服务
 * 处理边缘设备的自助注册、认证、凭证存储等功能
 */

import api from './api';

// 本地存储中的凭证key
const DEVICE_CREDENTIALS_KEY = 'mag_device_credentials';
const DEVICE_TOKEN_KEY = 'mag_device_token';

/**
 * 系统信息接口
 */
export interface SystemInfo {
  success: boolean;
  hostname: string;
  mac_address: string;
  device_id_suggestion: string;
  default_location: string;
}

/**
 * 设备凭证接口
 */
export interface DeviceCredentials {
  device_id: string;
  device_identifier: string;
  device_secret: string;
  status: 'pending' | 'approved' | 'active' | 'disabled';
  device_name: string;
  location?: string;
  mac_address?: string;
  ip_address?: string;
  registration_method: 'self_register' | 'admin_register';
  created_at: string;
  updated_at: string;
}

/**
 * 设备认证响应接口
 */
export interface DeviceAuthResponse {
  success: boolean;
  access_token: string;
  token_type: string;
  expires_in: number;
  device_info: {
    device_id: string;
    device_identifier: string;
    device_name: string;
    status: string;
    location?: string;
  };
}

/**
 * 设备状态接口
 */
export interface DeviceStatus {
  device_id: string;
  device_identifier: string;
  device_name: string;
  status: 'pending' | 'approved' | 'active' | 'disabled';
  location?: string;
  registration_method: string;
  created_at: string;
  approved_at?: string;
  activated_at?: string;
  message: string;
}

/**
 * 设备服务类
 */
class DeviceService {
  private baseURL: string;

  constructor(baseURL: string = '') {
    this.baseURL = baseURL;
  }

  /**
   * 获取系统信息（用于表单默认值）
   */
  async getSystemInfo(): Promise<SystemInfo> {
    try {
      const response = await api.get(`${this.baseURL}/device/system-info`);
      return response.data;
    } catch (error) {
      console.error('Failed to get system info:', error);
      // 返回默认值
      return {
        success: false,
        hostname: 'Unknown',
        mac_address: '00:00:00:00:00:00',
        device_id_suggestion: 'UUID-' + Math.random().toString(36).substr(2, 9),
        default_location: 'Chengdu'
      };
    }
  }

  /**
   * 设备自助注册
   * @param deviceIdentifier 设备标识符（MAC/SN/UUID）
   * @param psk 预共享密钥
   * @param deviceName 设备名称
   * @param location 设备位置（可选）
   */
  async selfRegisterDevice(
    deviceIdentifier: string,
    psk: string,
    deviceName: string,
    location?: string
  ) {
    try {
      const response = await api.post(`${this.baseURL}/device/self-register`, {
        device_identifier: deviceIdentifier,
        psk: psk,
        device_name: deviceName,
        location: location,
      });

      if (response.data.success) {
        const credentials: DeviceCredentials = {
          device_id: response.data.device.device_id,
          device_identifier: response.data.device.device_identifier,
          device_secret: response.data.device_secret,
          status: response.data.device.status,
          device_name: response.data.device.device_name,
          location: response.data.device.location,
          mac_address: response.data.device.mac_address,
          ip_address: response.data.device.ip_address,
          registration_method: response.data.device.registration_method,
          created_at: response.data.device.created_at,
          updated_at: response.data.device.updated_at,
        };

        // 保存凭证到本地存储
        this.saveCredentials(credentials);

        return {
          success: true,
          message: response.data.message,
          credentials,
        };
      } else {
        return {
          success: false,
          message: response.data.message,
        };
      }
    } catch (error: any) {
      console.error('Device self-register error:', error);
      throw {
        success: false,
        message: error.response?.data?.detail || '设备注册失败',
        error,
      };
    }
  }

  /**
   * 设备认证（获取JWT Token）
   * @param deviceId 设备ID
   * @param deviceSecret 设备密钥
   */
  async authenticateDevice(deviceId: string, deviceSecret: string) {
    try {
      const response = await api.post(`${this.baseURL}/device/authenticate`, {
        device_id: deviceId,
        device_secret: deviceSecret,
        grant_type: 'client_credentials',
      });

      if (response.data.success) {
        // 保存token到本地存储
        this.saveDeviceToken(response.data.access_token, response.data.expires_in);

        return {
          success: true,
          access_token: response.data.access_token,
          expires_in: response.data.expires_in,
          device_info: response.data.device_info,
        };
      } else {
        return {
          success: false,
          message: response.data.message,
        };
      }
    } catch (error: any) {
      console.error('Device authentication error:', error);
      throw {
        success: false,
        message: error.response?.data?.detail || '设备认证失败',
        error,
      };
    }
  }

  /**
   * 保存设备凭证到本地存储
   */
  saveCredentials(credentials: DeviceCredentials): void {
    try {
      localStorage.setItem(DEVICE_CREDENTIALS_KEY, JSON.stringify(credentials));
      console.log('Device credentials saved to localStorage');
    } catch (error) {
      console.error('Failed to save device credentials:', error);
    }
  }

  /**
   * 从本地存储获取设备凭证
   */
  getCredentials(): DeviceCredentials | null {
    try {
      const stored = localStorage.getItem(DEVICE_CREDENTIALS_KEY);
      if (stored) {
        return JSON.parse(stored);
      }
      return null;
    } catch (error) {
      console.error('Failed to get device credentials:', error);
      return null;
    }
  }

  /**
   * 清除本地设备凭证
   */
  clearCredentials(): void {
    try {
      localStorage.removeItem(DEVICE_CREDENTIALS_KEY);
      localStorage.removeItem(DEVICE_TOKEN_KEY);
      console.log('Device credentials cleared');
    } catch (error) {
      console.error('Failed to clear device credentials:', error);
    }
  }

  /**
   * 保存设备JWT token
   */
  saveDeviceToken(token: string, expiresIn: number): void {
    try {
      const expireTime = new Date().getTime() + expiresIn * 1000;
      localStorage.setItem(DEVICE_TOKEN_KEY, JSON.stringify({
        token,
        expireTime,
      }));
      console.log('Device token saved to localStorage');
    } catch (error) {
      console.error('Failed to save device token:', error);
    }
  }

  /**
   * 获取设备JWT token
   */
  getDeviceToken(): string | null {
    try {
      const stored = localStorage.getItem(DEVICE_TOKEN_KEY);
      if (stored) {
        const { token, expireTime } = JSON.parse(stored);
        // 检查token是否过期
        if (new Date().getTime() < expireTime) {
          return token;
        } else {
          // token已过期，清除
          localStorage.removeItem(DEVICE_TOKEN_KEY);
          return null;
        }
      }
      return null;
    } catch (error) {
      console.error('Failed to get device token:', error);
      return null;
    }
  }

  /**
   * 检查设备是否已注册
   */
  isDeviceRegistered(): boolean {
    return this.getCredentials() !== null;
  }

  /**
   * 获取设备状态
   */
  getDeviceStatus(): string {
    const credentials = this.getCredentials();
    if (!credentials) {
      return 'not_registered';
    }
    return credentials.status;
  }

  /**
   * 自动注册设备并获取token
   */
  async autoRegisterAndAuth(
    deviceIdentifier: string,
    psk: string,
    deviceName: string,
    location?: string
  ) {
    try {
      // 1. 先检查是否已注册
      const existingCredentials = this.getCredentials();
      if (existingCredentials && existingCredentials.device_id) {
        // 尝试使用现有凭证进行认证
        try {
          const authResult = await this.authenticateDevice(
            existingCredentials.device_id,
            existingCredentials.device_secret
          );
          if (authResult.success) {
            return {
              success: true,
              message: '使用已有凭证认证成功',
              credentials: existingCredentials,
            };
          }
        } catch (error) {
          console.log('Existing credentials authentication failed, attempting re-registration');
        }
      }

      // 2. 执行自助注册
      const registerResult = await this.selfRegisterDevice(
        deviceIdentifier,
        psk,
        deviceName,
        location
      );

      if (!registerResult.success) {
        throw new Error(registerResult.message);
      }

      return registerResult;
    } catch (error: any) {
      console.error('Auto register and auth error:', error);
      throw error;
    }
  }
}

// 导出单例
export const deviceService = new DeviceService();
