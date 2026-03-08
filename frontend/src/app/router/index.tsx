import { Suspense, lazy, type ReactNode } from "react";
import {
  Navigate,
  RouterProvider,
  createBrowserRouter,
} from "react-router-dom";

import { PrivateLayout } from "@/app/layouts/private-layout";
import { PublicLayout } from "@/app/layouts/public-layout";
import { ProtectedRoute } from "@/app/router/protected-route";
import { RootErrorBoundary } from "@/app/router/root-error";
import { Loading } from "@/shared/ui/loading";

const LoginPage = lazy(() => import("@/features/auth/pages/login-page").then((module) => ({ default: module.LoginPage })));
const RegisterPage = lazy(() =>
  import("@/features/auth/pages/register-page").then((module) => ({ default: module.RegisterPage })),
);
const ShareAccessPage = lazy(() =>
  import("@/features/share/pages/share-access-page").then((module) => ({ default: module.ShareAccessPage })),
);
const WorkspacePage = lazy(() =>
  import("@/features/workspace/pages/workspace-page").then((module) => ({ default: module.WorkspacePage })),
);
const DocumentsPage = lazy(() =>
  import("@/features/documents/pages/documents-page").then((module) => ({ default: module.DocumentsPage })),
);
const AnalysisPage = lazy(() =>
  import("@/features/analysis/pages/analysis-page").then((module) => ({ default: module.AnalysisPage })),
);

function withPageLoader(node: ReactNode) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center px-6 py-10">
          <Loading text="正在加载页面..." />
        </div>
      }
    >
      {node}
    </Suspense>
  );
}

const router = createBrowserRouter([
  {
    path: "/",
    errorElement: <RootErrorBoundary />,
    children: [
      {
        element: <PublicLayout />,
        children: [
          { path: "/login", element: withPageLoader(<LoginPage />) },
          { path: "/register", element: withPageLoader(<RegisterPage />) },
          { path: "/share/:token", element: withPageLoader(<ShareAccessPage />) },
        ],
      },
      {
        element: (
          <ProtectedRoute>
            <PrivateLayout />
          </ProtectedRoute>
        ),
        children: [
          { index: true, element: <Navigate to="/workspace" replace /> },
          { path: "/workspace", element: withPageLoader(<WorkspacePage />) },
          { path: "/documents", element: withPageLoader(<DocumentsPage />) },
          { path: "/analysis", element: withPageLoader(<AnalysisPage />) },
        ],
      },
      {
        path: "*",
        element: <Navigate to="/workspace" replace />,
      },
    ],
  },
]);

export function AppRouterProvider() {
  return <RouterProvider router={router} />;
}
