import { render } from "@testing-library/react";
import {
  createMemoryRouter,
  RouterProvider,
  type RouteObject,
} from "react-router";

export const renderWithRouter = ({
  routes,
  initialEntries = ["/"],
}: {
  routes: RouteObject[];
  initialEntries?: string[];
}) => {
  const router = createMemoryRouter(routes, { initialEntries });

  return {
    router,
    ...render(<RouterProvider router={router} />),
  };
};
