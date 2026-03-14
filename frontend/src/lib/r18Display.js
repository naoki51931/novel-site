import { useEffect, useState } from "react";

export const MYPAGE_SHOW_R18_STORAGE_KEY = "mypage_show_r18";
export const R18_DISPLAY_CHANGE_EVENT = "r18-display-setting-changed";

export const readShowR18Setting = () => {
  if (typeof window === "undefined") return true;
  const value = localStorage.getItem(MYPAGE_SHOW_R18_STORAGE_KEY);
  if (value === null) return true;
  return value === "1" || value === "true";
};

export const isR18Novel = (novel) =>
  String(novel?.age_limit || "all").toLowerCase() === "r18";

export const filterR18Novels = (items, showR18) => {
  const list = Array.isArray(items) ? items : [];
  if (showR18) return list;
  return list.filter((item) => !isR18Novel(item));
};

export const useShowR18ByDisplaySetting = () => {
  const [showR18, setShowR18] = useState(() => readShowR18Setting());

  useEffect(() => {
    const sync = () => setShowR18(readShowR18Setting());
    if (typeof window === "undefined") return undefined;
    window.addEventListener("storage", sync);
    window.addEventListener(R18_DISPLAY_CHANGE_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(R18_DISPLAY_CHANGE_EVENT, sync);
    };
  }, []);

  return showR18;
};
