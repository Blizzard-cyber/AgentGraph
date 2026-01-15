# 外部服务配置说明

## 配置方式

项目支持运行时配置外部服务地址（GpuStack和Higress Console），无需修改代码或重新打包前端。

## 配置文件位置

- **环境变量配置**: `docker/mag_services/.env`
- **运行时配置生成脚本**: `docker/mag_services/generate-config.sh`
- **前端配置模板**: `frontend/public/config.template.js`

## 相关环境变量

在 `.env` 文件中配置以下变量：

```bash
# GpuStack 平台配置
GPUSTACK_SERVICE_HOST=192.168.1.86
GPUSTACK_SERVICE_PORT=8899

# Higress 网关配置
HIGRESS_GATEWAY_HOST=192.168.1.85
HIGRESS_CONSOLE_PORT=8001
```

## 工作原理

1. **容器启动时**: nginx容器启动时，`generate-config.sh` 脚本自动执行
2. **生成配置**: 脚本读取环境变量，生成 `/usr/share/nginx/html/config.js`
3. **前端加载**: 前端页面加载时，先加载 `config.js`，将配置注入到 `window.APP_CONFIG`
4. **代码读取**: 前端代码从 `window.APP_CONFIG` 读取配置

## 修改配置步骤

### 方法1: 修改环境变量文件（推荐）

1. 编辑 `docker/mag_services/.env` 文件
2. 修改相关的主机和端口配置
3. 重启nginx容器：
   ```bash
   cd docker/mag_services
   docker-compose restart nginx
   ```

### 方法2: 直接修改配置文件

如果容器已经在运行，可以直接修改生成的配置文件：

```bash
# 进入容器
docker exec -it mag-nginx sh

# 编辑配置文件
vi /usr/share/nginx/html/config.js

# 修改后无需重启，刷新浏览器即可
```

## 开发环境

开发环境可以使用 `frontend/.env` 文件配置：

```bash
VITE_GPUSTACK_SERVICE_HOST=192.168.1.86
VITE_GPUSTACK_SERVICE_PORT=8899
VITE_HIGRESS_CONSOLE_HOST=192.168.1.85
VITE_HIGRESS_CONSOLE_PORT=8001
```

## 验证配置

打开浏览器控制台，输入：
```javascript
console.log(window.APP_CONFIG);
```

应该能看到当前加载的配置。
