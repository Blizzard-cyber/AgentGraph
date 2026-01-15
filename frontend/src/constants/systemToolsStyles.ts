// src/constants/systemToolsStyles.ts

/**
 * 系统工具管理器样式常量
 */

export const COLORS = {
  primary: '#1890ff',
  secondary: '#1890ff',
  tertiary: '#1890ff',
  text: 'rgba(0, 0, 0, 0.85)',
  textSecondary: 'rgba(0, 0, 0, 0.65)',
  textLight: 'rgba(0, 0, 0, 0.45)',
  background: '#ffffff',
  backgroundLight: '#fafafa',
  white: '#ffffff',
  whiteLight: '#ffffff',
  border: '#d9d9d9',
  borderLight: '#f0f0f0',
  borderPrimary: '#91caff',
  shadow: 'rgba(0, 0, 0, 0.03)',
  shadowHover: 'rgba(0, 0, 0, 0.08)'
};

export const TAG_STYLES = {
  primary: {
    background: '#e6f4ff',
    color: COLORS.primary,
    border: `1px solid ${COLORS.borderPrimary}`,
    borderRadius: '4px',
    fontWeight: 500,
    padding: '2px 8px',
    fontSize: '12px'
  },
  secondary: {
    background: 'rgba(24, 144, 255, 0.08)',
    color: COLORS.secondary,
    border: '1px solid #91caff',
    borderRadius: '4px',
    fontWeight: 500,
    padding: '2px 8px',
    fontSize: '12px'
  },
  tertiary: {
    background: 'rgba(24, 144, 255, 0.08)',
    color: COLORS.tertiary,
    border: '1px solid #91caff',
    borderRadius: '4px',
    fontSize: '11px',
    padding: '2px 6px'
  },
  required: {
    background: '#e6f4ff',
    color: COLORS.primary,
    border: `1px solid ${COLORS.borderPrimary}`,
    borderRadius: '4px',
    fontSize: '11px',
    padding: '2px 6px'
  }
};

export const CARD_STYLES = {
  base: {
    borderRadius: '4px',
    border: `1px solid ${COLORS.border}`,
    boxShadow: `0 1px 2px ${COLORS.shadow}`,
    background: COLORS.white,
    transition: 'all 0.3s cubic-bezier(0.23, 1, 0.32, 1)',
    height: '100%',
    display: 'flex',
    flexDirection: 'column' as const
  },
  hover: {
    transform: 'translateY(-2px)',
    boxShadow: `0 6px 16px 0 ${COLORS.shadowHover}, 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)`,
    borderColor: '#d9d9d9'
  }
};

export const BUTTON_STYLES = {
  icon: {
    padding: '4px',
    borderRadius: '4px',
    color: 'rgba(0, 0, 0, 0.65)',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'transparent'
  },
  iconHover: {
    color: COLORS.primary,
    background: '#e6f4ff'
  }
};
