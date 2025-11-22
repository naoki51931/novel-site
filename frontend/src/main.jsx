import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

// すべての <a> と <button> に自動で btn btn-border を付ける
function applyGlobalButtonClasses() {
  document
    .querySelectorAll("a:not(.btn-border), button:not(.btn-border)")
    .forEach((el) => {
      el.classList.add("btn", "btn-border");
    });
}

// 初回ロード時
window.addEventListener("DOMContentLoaded", applyGlobalButtonClasses);

// React の更新時にも再適用
const observer = new MutationObserver(applyGlobalButtonClasses);
observer.observe(document.body, { childList: true, subtree: true });

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
