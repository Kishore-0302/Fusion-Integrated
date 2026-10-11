import type { RouteObject } from "react-router-dom";
import ElmPage from "./ElmPage";

export const routes: RouteObject[] = [
  {
    path: "/elm",
    element: <ElmPage />,
  },
];
