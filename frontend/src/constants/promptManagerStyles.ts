/**
 * Prompt Manager 样式常量
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
    fontSize: '13px',
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
};

export const BUTTON_STYLES = {
  primary: {
    background: '#1890ff',
    border: 'none',
    borderRadius: '4px',
    color: '#fff',
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: 500,
    letterSpacing: '0.3px',
    boxShadow: '0 2px 0 rgba(0, 0, 0, 0.016)',
    transition: 'all 0.3s cubic-bezier(0.23, 1, 0.32, 1)',
  },
  secondary: {
    color: 'rgba(0, 0, 0, 0.65)',
    background: 'transparent',
    borderRadius: '4px',
    transition: 'all 0.2s ease',
  },
};

export const INPUT_STYLES = {
  search: {
    width: 240,
    height: '32px',
    padding: '4px 11px',
    borderRadius: '4px',
    border: '1px solid #d9d9d9',
    background: '#ffffff',
    boxShadow: 'none',
    fontSize: '14px',
    color: 'rgba(0, 0, 0, 0.85)',
    letterSpacing: '0.3px',
    transition: 'all 0.3s ease',
  },
};

export const CARD_STYLES = {
  base: {
    borderRadius: '6px',
    border: '1px solid rgba(24, 144, 255, 0.15)',
    boxShadow: '0 1px 3px rgba(24, 144, 255, 0.06)',
    transition: 'all 0.3s cubic-bezier(0.23, 1, 0.32, 1)',
    background: COLORS.whiteTransparent,
    height: '100%',
  },
  hover: {
    transform: 'translateY(-2px)',
    boxShadow: '0 4px 12px rgba(24, 144, 255, 0.12)',
    borderColor: 'rgba(24, 144, 255, 0.3)',
  },
};

export const ACTION_BUTTON_STYLES = {
  base: {
    color: COLORS.secondary,
    transition: 'all 0.2s ease',
    cursor: 'pointer',
    padding: '4px',
    borderRadius: '4px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  hover: {
    color: COLORS.primary,
    background: COLORS.primaryLight,
  },
};

export const MODAL_STYLES = {
  wrapper: {
    maxHeight: '90vh',
    top: '5vh',
  },
  body: {
    height: 'calc(85vh - 120px)',
    padding: 0,
    overflow: 'hidden' as const,
  },
  form: {
    height: '100%',
    display: 'flex',
    flexDirection: 'column' as const,
  },
  basicInfo: {
    padding: '24px 24px 0',
    flexShrink: 0,
  },
  contentArea: {
    flex: 1,
    padding: '0 24px',
    display: 'flex',
    flexDirection: 'column' as const,
    minHeight: 0,
  },
  footer: {
    padding: '16px 24px 24px',
    borderTop: '1px solid rgba(24, 144, 255, 0.15)',
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '8px',
    flexShrink: 0,
  },
};

export const COLLAPSE_STYLES = {
  panel: {
    marginBottom: '16px',
    borderRadius: '8px',
    border: '1px solid rgba(24, 144, 255, 0.15)',
    background: 'rgba(230, 244, 255, 0.6)',
    overflow: 'hidden' as const,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '4px 0',
  },
  headerText: {
    fontSize: '14px',
    color: COLORS.text,
    fontWeight: 500,
    letterSpacing: '0.3px',
    flex: 1,
  },
};
