// 管理面板样式常量
export const COLORS = {
  primary: '#1890ff',
  secondary: '#40a9ff',
  tertiary: '#1890ff',
  text: 'rgba(0, 0, 0, 0.85)',
  textSecondary: 'rgba(0, 0, 0, 0.65)',
  textLight: 'rgba(0, 0, 0, 0.65)',
  success: '#54cc98',
  background: '#ffffff',
  white: '#fff',
  whiteAlpha85: '#ffffff',
  whiteAlpha90: '#ffffff',
  whiteAlpha95: '#ffffff',
  whiteAlpha98: '#ffffff',
  backgroundLight: '#fafafa',
  backgroundCard: '#ffffff',
};

export const GRADIENTS = {
  primary: '#1890ff',
  header: '#ffffff',
  decorativeLine: 'transparent',
};

export const SHADOWS = {
  card: '0 1px 2px rgba(0, 0, 0, 0.03)',
  button: '0 2px 0 rgba(0, 0, 0, 0.016)',
  buttonSmall: 'none',
  modal: '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
  input: 'none',
  inputFocus: '0 0 0 2px rgba(24, 144, 255, 0.2)',
};

export const BORDERS = {
  light: '1px solid #f0f0f0',
  normal: '1px solid #d9d9d9',
  medium: '1px solid #d9d9d9',
  strong: '1px solid #d9d9d9',
};

/**
 * 获取标签样式
 */
export const getTagStyle = (color: string) => ({
  background: `${color}20`,
  color: color,
  border: `1px solid ${color}40`,
  borderRadius: '4px',
  fontWeight: 500,
  padding: '2px 8px',
});

/**
 * 获取状态标签样式
 */
export const getStatusTagStyle = (isActive: boolean) => ({
  background: isActive ? '#f0fff6' : 'rgba(0, 0, 0, 0.04)',
  color: isActive ? COLORS.success : 'rgba(0, 0, 0, 0.45)',
  border: `1px solid ${isActive ? '#b7eb8f' : '#d9d9d9'}`,
  borderRadius: '4px',
  fontWeight: 500,
  padding: '2px 8px',
});

/**
 * 获取主按钮样式
 */
export const getPrimaryButtonStyle = (size: 'small' | 'default' = 'default') => ({
  background: '#1890ff',
  border: 'none',
  color: COLORS.white,
  borderRadius: '4px',
  fontSize: size === 'small' ? '12px' : '14px',
  fontWeight: 500,
  boxShadow: SHADOWS.button,
  height: size === 'small' ? '24px' : '32px',
  padding: size === 'small' ? '0 8px' : '0 16px',
});

/**
 * 获取次要按钮样式
 */
export const getSecondaryButtonStyle = (size: 'small' | 'default' = 'default') => ({
  borderRadius: '4px',
  height: size === 'small' ? '24px' : '32px',
  padding: size === 'small' ? '0 8px' : '0 16px',
  border: BORDERS.medium,
  background: COLORS.white,
  color: 'rgba(0, 0, 0, 0.65)',
  fontSize: size === 'small' ? '12px' : '14px',
  fontWeight: 500,
  boxShadow: SHADOWS.buttonSmall,
  transition: 'all 0.3s ease',
});

/**
 * 获取输入框样式
 */
export const getInputStyle = () => ({
  height: '40px',
  borderRadius: '6px',
  border: BORDERS.medium,
  background: COLORS.whiteAlpha90,
  boxShadow: SHADOWS.input,
  fontSize: '14px',
  color: COLORS.text,
  letterSpacing: '0.3px',
  transition: 'all 0.3s ease',
});

/**
 * 获取输入框焦点样式
 */
export const getInputFocusStyle = () => ({
  borderColor: COLORS.primary,
  boxShadow: SHADOWS.inputFocus,
  background: COLORS.whiteAlpha98,
});

/**
 * 获取输入框失焦样式
 */
export const getInputBlurStyle = () => ({
  borderColor: 'rgba(24, 144, 255, 0.2)',
  boxShadow: SHADOWS.input,
  background: COLORS.whiteAlpha90,
});

/**
 * 获取用户头像样式
 */
export const getUserAvatarStyle = () => ({
  width: '36px',
  height: '36px',
  borderRadius: '50%',
  background: GRADIENTS.primary,
  color: COLORS.white,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '14px',
  fontWeight: 500,
  boxShadow: SHADOWS.button,
});

/**
 * 获取代码块样式
 */
export const getCodeStyle = () => ({
  background: 'rgba(24, 144, 255, 0.08)',
  color: COLORS.primary,
  padding: '6px 12px',
  borderRadius: '6px',
  fontSize: '13px',
  fontWeight: 500,
  border: BORDERS.medium,
  fontFamily: 'monospace',
});

/**
 * 获取Modal样式配置
 */
export const getModalStyles = () => ({
  mask: {
    backdropFilter: 'blur(8px)',
    background: 'rgba(24, 144, 255, 0.15)',
  },
  content: {
    borderRadius: '8px',
    overflow: 'hidden',
    boxShadow: SHADOWS.modal,
    border: BORDERS.light,
  },
  header: {
    borderBottom: BORDERS.light,
    padding: '18px 24px',
    marginBottom: 0,
  },
  body: {
    background: COLORS.whiteAlpha98,
    padding: '24px',
  },
  footer: {
    padding: '14px 20px',
    marginTop: 0,
  },
});

/**
 * 获取确认Modal样式配置
 */
export const getConfirmModalStyles = () => ({
  mask: {
    backdropFilter: 'blur(8px)',
    background: 'rgba(24, 144, 255, 0.15)',
  },
});
