#!/bin/sh
# Generate runtime configuration from environment variables

cat > /usr/share/nginx/html/config.js <<EOF
// Runtime configuration - Generated from environment variables
window.APP_CONFIG = {
  externalServices: {
    gpuStack: {
      host: '${GPUSTACK_SERVICE_HOST:-192.168.1.90}',
      port: '${GPUSTACK_SERVICE_PORT:-8899}',
      url: 'http://${GPUSTACK_SERVICE_HOST:-192.168.1.90}:${GPUSTACK_SERVICE_PORT:-8899}'
    },
    higressConsole: {
      host: '${HIGRESS_GATEWAY_HOST:-192.168.1.85}',
      port: '${HIGRESS_CONSOLE_PORT:-8001}',
      url: 'http://${HIGRESS_GATEWAY_HOST:-192.168.1.85}:${HIGRESS_CONSOLE_PORT:-8001}'
    }
  }
};
EOF

echo "Runtime configuration generated successfully"
cat /usr/share/nginx/html/config.js

# Start nginx
exec nginx -g 'daemon off;'
