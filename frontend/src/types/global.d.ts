export {};

declare global {
  interface Error {
    code?: string;
    handled?: boolean;
  }

  interface Window {
    AndroidFormBridge?: {
      notifySiteNotification?: (payload: string) => void;
      notifyAiGeneration?: (payload: string) => void;
      registerMobilePush?: (token: string) => void;
    };
    __lexisFetchHeaderInstalled?: boolean;
    gtag?: (...args: any[]) => void;
    grecaptcha?: {
      ready?: (callback: () => void) => void;
      execute?: (siteKey: string, options: { action: string }) => Promise<string>;
      enterprise?: {
        ready: (callback: () => void) => void;
        execute: (siteKey: string, options: { action: string }) => Promise<string>;
      };
    };
  }
}
