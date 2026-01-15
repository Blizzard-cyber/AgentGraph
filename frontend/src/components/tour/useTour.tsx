// src/components/tour/useTour.tsx
import { useEffect, useRef, useCallback } from 'react';
import { driver, DriveStep, Config } from 'driver.js';
import 'driver.js/dist/driver.css';
import './tour.css';
import { useT } from '../../i18n/hooks';

export interface TourStep {
  element: string;
  titleKey: string;
  contentKey: string;
  placement?: 'top' | 'bottom' | 'left' | 'right' | 'center';
}

interface UseTourOptions {
  steps: TourStep[];
  onComplete?: () => void;
  onSkip?: () => void;
}

export const useTour = ({ steps, onComplete, onSkip }: UseTourOptions) => {
  const t = useT();
  const driverRef = useRef<ReturnType<typeof driver> | null>(null);

  useEffect(() => {
    // 自定义样式配置
    const customConfig: Config = {
      showProgress: true,
      showButtons: ['next', 'previous', 'close'],
      progressText: '{{current}}/{{total}}',
      nextBtnText: t('components.tour.nextBtn') || '下一步',
      prevBtnText: t('components.tour.prevBtn') || '上一步',
      doneBtnText: t('components.tour.doneBtn') || '完成',
      animate: true,
      overlayOpacity: 0.7,
      smoothScroll: true,
      disableActiveInteraction: false,
      allowClose: true,
      overlayColor: '#000',
      stagePadding: 8,
      stageRadius: 8,
      onCloseClick: () => {
        if (driverRef.current) {
          if (onSkip) {
            const currentIndex = driverRef.current.getActiveIndex();
            if (currentIndex !== undefined && currentIndex < steps.length - 1) {
              onSkip();
            }
          }
          driverRef.current.destroy();
        }
      },
      onNextClick: () => {
        if (!driverRef.current) return;
        
        const currentIndex = driverRef.current.getActiveIndex();
        if (currentIndex !== undefined && currentIndex === steps.length - 1) {
          // 最后一步，点击完成
          driverRef.current.destroy();
          if (onComplete) {
            onComplete();
          }
        } else {
          // 继续下一步
          driverRef.current.moveNext();
        }
      },
      onPrevClick: () => {
        if (driverRef.current) {
          driverRef.current.movePrevious();
        }
      },
      onDestroyed: () => {
        // 引导被销毁时触发
      }
    };

    // 转换步骤为driver.js格式
    const driveSteps: DriveStep[] = steps.map((step) => {
      let side: 'top' | 'bottom' | 'left' | 'right' = 'bottom';
      if (step.placement && ['top', 'bottom', 'left', 'right'].includes(step.placement)) {
        side = step.placement as 'top' | 'bottom' | 'left' | 'right';
      }
      return {
        element: step.element,
        popover: {
          title: t(step.titleKey),
          description: t(step.contentKey),
          side: side,
          align: 'start'
        }
      };
    });

    driverRef.current = driver({
      ...customConfig,
      steps: driveSteps
    });

    return () => {
      if (driverRef.current) {
        driverRef.current.destroy();
      }
    };
  }, [steps, t, onComplete, onSkip]);

  const startTour = useCallback(() => {
    if (driverRef.current) {
      driverRef.current.drive();
    }
  }, []);

  const stopTour = useCallback(() => {
    if (driverRef.current) {
      driverRef.current.destroy();
    }
  }, []);

  return { startTour, stopTour };
};
