/** Frontend module registry.
 *
 *  `code` MUST match accesscontrol_module.code on the server. An ungranted
 *  module gets no route at all, so deep-linking it 404s rather than rendering
 *  blank. `load` must be a STATIC import() literal or Vite cannot split it. */
import type { RouteObject } from "react-router-dom";

export interface ModuleManifest {
  code: string;
  basePath: string;
  load: () => Promise<{ routes: RouteObject[] }>;
}

export const MODULE_REGISTRY: Record<string, ModuleManifest> = {
  placement_cell: {
    code: "placement_cell",
    basePath: "/placement",
    load: () => import("../modules/placement/routes"),
  },
  elm: {
    code: "elm",
    basePath: "/elm",
    load: () => import("../modules/elm/routes"),
  },
};
