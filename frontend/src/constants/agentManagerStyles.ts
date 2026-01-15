/**
 * Agent Manager 样式常量
 * 统一管理所有样式配置，提升可维护性
 */

export const COLORS = {
  primary: '#1890ff',
  primaryLight: '#e6f4ff',
  primaryBorder: '#91caff',
  secondary: '#1890ff',
  secondaryLight: 'rgba(24, 144, 255, 0.08)',
  secondaryBorder: '#d9d9d9',
  text: 'rgba(0, 0, 0, 0.85)',
  textLight: 'rgba(0, 0, 0, 0.65)',
  textMuted: 'rgba(0, 0, 0, 0.45)',
  background: '#ffffff',
  backgroundLight: '#fafafa',
  white: '#fff',
  whiteTransparent: '#ffffff',
} as const;

export const HEADER_STYLES = {
  container: {
    background: '#ffffff',
    backdropFilter: 'none',
    padding: '0 48px',
    borderBottom: '1px solid #d9d9d9',
    boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
    position: 'relative' as const,
  },
  decorativeLine: {
    display: 'none',
  },
  title: {
    margin: 0,
    color: 'rgba(0, 0, 0, 0.85)',
    fontWeight: 500,
    letterSpacing: '0.5px',
    fontSize: '16px',
  },
};

export const TAG_STYLES = {
  primary: {
    background: COLORS.primaryLight,
    color: COLORS.primary,
    border: `1px solid ${COLORS.primaryBorder}`,
    borderRadius: '6px',
    fontWeight: 500,
    padding: '4px 12px',
    fontSize: '12px',
  },
  secondary: {
    background: COLORS.secondaryLight,
    color: COLORS.secondary,
    border: `1px solid ${COLORS.secondaryBorder}`,
    borderRadius: '6px',
    fontWeight: 500,
    padding: '4px 12px',
    fontSize: '12px',
  },
  dashed: {
    background: 'transparent',
    color: COLORS.textMuted,
    border: `1px dashed ${COLORS.secondaryBorder}`,
    borderRadius: '4px',
    fontWeight: 500,
    fontSize: '12px',
    padding: '2px 8px',
    margin: 0,
    lineHeight: '1.4',
  },
};

export const BUTTON_STYLES = {
  primary: {
    background: '#1890ff',
    border: 'none',
    borderRadius: '4px',
    color: '#fff',
    fontWeight: 500,
    fontSize: '14px',
    letterSpacing: '0.3px',
    boxShadow: '0 2px 0 rgba(0, 0, 0, 0.016)',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '0 16px',
  },
  secondary: {
    borderRadius: '4px',
    border: '1px solid #d9d9d9',
    background: '#ffffff',
    color: 'rgba(0, 0, 0, 0.65)',
    fontWeight: 500,
    fontSize: '14px',
    letterSpacing: '0.3px',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '0 16px',
  },
};

export const INPUT_STYLES = {
  base: {
    borderRadius: '4px',
    border: '1px solid #d9d9d9',
    background: '#ffffff',
    boxShadow: 'none',
    fontSize: '14px',
    color: 'rgba(0, 0, 0, 0.85)',
    letterSpacing: '0.3px',
  },
  focus: {
    borderColor: '#1890ff',
    boxShadow: '0 0 0 2px rgba(24, 144, 255, 0.2)',
  },
  blur: {
    borderColor: '#d9d9d9',
    boxShadow: 'none',
  },
};

export const CARD_STYLES = {
  base: {
    borderRadius: '4px',
    border: '1px solid #d9d9d9',
    boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
    transition: 'all 0.3s cubic-bezier(0.23, 1, 0.32, 1)',
    background: '#ffffff',
    height: '100%',
  },
  hover: {
    transform: 'translateY(-2px)',
    boxShadow: '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
    borderColor: '#d9d9d9',
  },
  iconContainer: {
    flexShrink: 0,
    width: '48px',
    height: '48px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: COLORS.primaryLight,
    borderRadius: '8px',
    border: `1px solid rgba(24, 144, 255, 0.1)`,
  },
};

export const ACTION_BUTTON_STYLES = {
  base: {
    color: COLORS.secondary,
    transition: 'all 0.2s ease',
    cursor: 'pointer',
    padding: '8px',
    borderRadius: '6px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: `1px solid rgba(24, 144, 255, 0.15)`,
  },
  hover: {
    color: COLORS.primary,
    background: COLORS.primaryLight,
    borderColor: COLORS.primaryBorder,
  },
  delete: {
    color: COLORS.primary,
    border: `1px solid rgba(24, 144, 255, 0.15)`,
  },
  deleteHover: {
    color: '#d4574a',
    background: 'rgba(24, 144, 255, 0.12)',
    borderColor: 'rgba(24, 144, 255, 0.3)',
  },
};

export const MODAL_STYLES = {
  content: {
    borderRadius: '10px',
    boxShadow: '0 12px 40px rgba(24, 144, 255, 0.2)',
    padding: 0,
    overflow: 'hidden',
  },
  header: {
    background: 'linear-gradient(to bottom, rgba(230, 244, 255, 0.95), rgba(255, 255, 255, 0.9))',
    borderBottom: `1px solid rgba(24, 144, 255, 0.12)`,
    padding: '18px 28px',
    marginBottom: 0,
  },
  body: {
    padding: '28px 28px 20px',
    background: '#fff',
    maxHeight: '70vh',
    overflowY: 'auto' as const,
  },
  footer: {
    borderTop: `1px solid rgba(24, 144, 255, 0.12)`,
    padding: '16px 28px',
    background: 'rgba(230, 244, 255, 0.3)',
    marginTop: 0,
  },
};

export const FORM_SECTION_STYLES = {
  container: {
    background: 'rgba(230, 244, 255, 0.3)',
    padding: '16px 20px',
    borderRadius: '8px',
    marginBottom: '20px',
    border: `1px solid rgba(24, 144, 255, 0.1)`,
  },
  title: {
    fontSize: '13px',
    fontWeight: 600,
    color: COLORS.primary,
    marginBottom: '16px',
    letterSpacing: '0.5px',
    textTransform: 'uppercase' as const,
  },
  label: {
    color: COLORS.textLight,
    fontWeight: 500,
    fontSize: '14px',
  },
};
