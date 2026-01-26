// Small helper utilities for Zustand stores

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const updateZustandState = (store: any, updater: (state: any) => any) => {
  if (store && typeof store.setState === 'function') {
    store.setState(updater);
  }
};
