import { StrictMode } from "react";
import ReactDOM from "react-dom/client";

import "@/index.css";
import { AppRouterProvider } from "@/app/router";
import { AppProviders } from "@/app/providers/app-provider";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProviders>
      <AppRouterProvider />
    </AppProviders>
  </StrictMode>,
);
