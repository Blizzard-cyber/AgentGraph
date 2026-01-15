// MCP管理器样式常量
export const MCP_COLORS = {
  primary: '#1890ff',
  secondary: '#40a9ff',
  tertiary: '#1890ff',
  text: 'rgba(0, 0, 0, 0.85)',
  textSecondary: 'rgba(0, 0, 0, 0.65)',
  textLight: 'rgba(0, 0, 0, 0.65)',
  textPlaceholder: 'rgba(0, 0, 0, 0.25)',
  success: '#54cc98',
  warning: '#faad14',
  background: '#ffffff',
  white: '#fff',
  whiteAlpha85: '#ffffff',
  whiteAlpha90: '#ffffff',
  whiteAlpha95: '#ffffff',
  whiteAlpha98: '#ffffff',
  backgroundLight: '#fafafa',
  backgroundCard: '#ffffff',
  backgroundNote: '#fafafa',
};

export const MCP_GRADIENTS = {
  primary: '#1890ff',
  header: '#ffffff',
  decorativeLine: 'transparent',
};

export const MCP_SHADOWS = {
  card: '0 1px 2px rgba(0, 0, 0, 0.03)',
  button: '0 2px 0 rgba(0, 0, 0, 0.016)',
  buttonHover: '0 6px 16px rgba(0, 0, 0, 0.08)',
  buttonSmall: 'none',
  modal: '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
  input: 'none',
  inputFocus: '0 0 0 2px rgba(24, 144, 255, 0.2)',
  buttonInset: 'none',
  buttonInsetHover: 'none',
};

export const MCP_BORDERS = {
  light: '1px solid #f0f0f0',
  lightMedium: '1px solid #d9d9d9',
  normal: '1px solid #d9d9d9',
  medium: '1px solid #d9d9d9',
  strong: '1px solid #d9d9d9',
  primary: '1px solid #1890ff',
  warning: '1px solid #faad14',
};

/**
 * 获取标签样式
 */
export const getMCPTagStyle = (color: string, opacity: string = '0.08') => ({
  background: `${color}20`,
  color: color,
  border: `1px solid ${color}40`,
  borderRadius: '4px',
  fontWeight: 500,
  padding: '2px 8px',
  fontSize: '12px',
});

/**
 * 获取主按钮样式
 */
export const getMCPPrimaryButtonStyle = () => ({
  flex: 1,
  background: '#1890ff',
  border: 'none',
  borderRadius: '4px',
  color: '#ffffff',
  padding: '8px 16px',
  fontSize: '14px',
  fontWeight: 500,
  letterSpacing: '0.3px',
  boxShadow: '0 2px 0 rgba(0, 0, 0, 0.016)',
  transition: 'all 0.3s cubic-bezier(0.23, 1, 0.32, 1)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '6px',
  height: '32px',
});

/**
 * 获取次要按钮样式
 */
export const getMCPSecondaryButtonStyle = () => ({
  flex: 1,
  height: '32px',
  borderRadius: '4px',
  border: '1px solid #d9d9d9',
  background: '#ffffff',
  color: 'rgba(0, 0, 0, 0.65)',
  fontSize: '14px',
  fontWeight: 500,
  letterSpacing: '0.3px',
  boxShadow: 'none',
  transition: 'all 0.3s ease',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '6px',
});

/**
 * 获取边框按钮样式
 */
export const getMCPOutlineButtonStyle = () => ({
  flex: 1,
  height: '36px',
  borderRadius: '6px',
  border: MCP_BORDERS.primary,
  background: 'transparent',
  color: MCP_COLORS.primary,
  fontSize: '14px',
  fontWeight: 500,
  letterSpacing: '0.3px',
  boxShadow: '0 1px 3px rgba(24, 144, 255, 0.1)',
  transition: 'all 0.3s ease',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '6px',
});

/**
 * 获取视图切换按钮样式
 */
export const getMCPViewSwitchButtonStyle = () => ({
  height: '36px',
  borderRadius: '6px',
  border: MCP_BORDERS.medium,
  background: MCP_COLORS.whiteAlpha85,
  color: MCP_COLORS.tertiary,
  fontSize: '14px',
  fontWeight: 500,
  letterSpacing: '0.3px',
  boxShadow: MCP_SHADOWS.buttonSmall,
  transition: 'all 0.3s ease',
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
});

/**
 * 获取输入框样式
 */
export const getMCPInputStyle = () => ({
  height: '40px',
  borderRadius: '6px',
  border: MCP_BORDERS.medium,
  background: MCP_COLORS.whiteAlpha85,
  boxShadow: MCP_SHADOWS.input,
  fontSize: '14px',
  color: MCP_COLORS.text,
  letterSpacing: '0.3px',
});

/**
 * 获取文本域样式
 */
export const getMCPTextAreaStyle = () => ({
  borderRadius: '6px',
  border: MCP_BORDERS.medium,
  background: MCP_COLORS.whiteAlpha85,
  boxShadow: MCP_SHADOWS.input,
  fontSize: '14px',
  color: MCP_COLORS.text,
  letterSpacing: '0.3px',
  resize: 'vertical' as const,
});

/**
 * 获取代码文本域样式
 */
export const getMCPCodeTextAreaStyle = () => ({
  ...getMCPTextAreaStyle(),
  fontFamily: 'Monaco, "Courier New", monospace',
  fontSize: '13px',
  letterSpacing: '0.2px',
});

/**
 * 获取标签样式
 */
export const getMCPLabelStyle = () => ({
  display: 'block',
  marginBottom: '8px',
  fontSize: '14px',
  fontWeight: 500,
  color: MCP_COLORS.text,
  letterSpacing: '0.3px',
});

/**
 * 获取空状态容器样式
 */
export const getMCPEmptyStateStyle = () => ({
  textAlign: 'center' as const,
  padding: '80px 20px',
  background: 'rgba(230, 244, 255, 0.6)',
  borderRadius: '8px',
  border: MCP_BORDERS.normal,
});
