/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // GPUStack统一主题色
        primary: {
          DEFAULT: '#1890ff',
          50: '#f6f8fc',
          100: '#e6f4ff',
          200: '#bae0ff',
          300: '#91caff',
          400: '#69b1ff',
          500: '#1890ff',
          600: '#0050b3',
        },
        slate: {
          DEFAULT: '#595959',
          50: '#f9f9f9',
          100: '#f4f5f4',
          200: '#e8e8e8',
          300: '#d9d9d9',
          400: '#bfbfbf',
          500: '#8c8c8c',
          600: '#595959',
          700: '#434343',
        },
        gray: {
          DEFAULT: '#8c8c8c',
          50: '#ffffff',
          100: '#fafafa',
          200: '#f5f5f5',
          300: '#f0f0f0',
          400: '#d9d9d9',
          500: '#bfbfbf',
          600: '#8c8c8c',
          700: '#595959',
        },
        success: {
          DEFAULT: '#54cc98',
          light: '#f0fff6',
          bg: '#f0fff6',
        },
        warning: {
          DEFAULT: '#faad14',
          light: '#fffbe6',
        },
        error: {
          DEFAULT: '#ff4d4f',
          light: '#fff2f0',
          bg: '#fff2f0',
        },
        ink: {
          DEFAULT: '#262626',
          light: 'rgba(0, 0, 0, 0.85)',
          lighter: 'rgba(0, 0, 0, 0.65)',
          lightest: 'rgba(0, 0, 0, 0.45)',
        },
        paper: '#ffffff',
        cream: '#fafafa',
        sider: '#ffffff',
        bg: '#ffffff',
      },
      boxShadow: {
        'card': '0 1px 2px rgba(0, 0, 0, 0.03)',
        'card-hover': '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
        'button': '0 2px 0 rgba(0, 0, 0, 0.016)',
        'button-hover': '0 6px 16px rgba(0, 0, 0, 0.08)',
        'input': '0 0 0 1px rgba(24, 144, 255, 0)',
        'input-focus': '0 0 0 2px rgba(24, 144, 255, 0.2)',
        'header': '0 1px 2px rgba(0, 0, 0, 0.03)',
        'secondary': '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
      },
      borderRadius: {
        'card': '4px',
        'button': '4px',
        'input': '4px',
        'base': '4px',
        'modal': '12px',
      },
      backdropBlur: {
        'glass': '20px',
      },
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.23, 1, 0.32, 1)',
      },
    },
  },
  plugins: [],
}