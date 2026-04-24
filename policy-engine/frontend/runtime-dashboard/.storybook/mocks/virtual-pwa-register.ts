type RegisterSwOptions = {
  immediate?: boolean;
};

export function registerSW(_options?: RegisterSwOptions) {
  return async (_reloadPage?: boolean): Promise<void> => {};
}

export function useRegisterSW() {
  return {
    updateServiceWorker: async () => {
      return;
    },
  };
}
