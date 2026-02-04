/**
 * 外部服务配置
 * 从运行时配置中读取，支持打包后修改配置
 */

export interface ExternalServiceConfig {
  gpuStack: {
    host: string;
    port: string;
    url: string;
  };
  higressConsole: {
    host: string;
    port: string;
    url: string;
  };
}

// 声明全局配置对象
declare global {
  interface Window {
    APP_CONFIG?: {
      externalServices: ExternalServiceConfig;
    };
  }
}

/**
 * 获取外部服务配置
 * 优先从 window.APP_CONFIG 读取（运行时配置）
 * 其次从环境变量读取（开发环境）
 * 最后使用默认值
 */
export const getExternalServices = (): ExternalServiceConfig => {
  // 如果存在运行时配置，直接使用
  if (window.APP_CONFIG?.externalServices) {
    return window.APP_CONFIG.externalServices;
  }

  // 开发环境从环境变量读取
  const gpuStackHost = import.meta.env.VITE_GPUSTACK_SERVICE_HOST || '192.168.1.90';
  const gpuStackPort = import.meta.env.VITE_GPUSTACK_SERVICE_PORT || '8899';
  const higressHost = import.meta.env.VITE_HIGRESS_CONSOLE_HOST || '192.168.1.85';
  const higressPort = import.meta.env.VITE_HIGRESS_CONSOLE_PORT || '8001';

  return {
    gpuStack: {
      host: gpuStackHost,
      port: gpuStackPort,
      url: `http://${gpuStackHost}:${gpuStackPort}`,
    },
    higressConsole: {
      host: higressHost,
      port: higressPort,
      url: `http://${higressHost}:${higressPort}`,
    },
  };
};
