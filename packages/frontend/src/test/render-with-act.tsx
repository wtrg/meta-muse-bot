import { act, render } from "@testing-library/react";
import type { RenderOptions, RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";

export async function renderWithAct(ui: ReactElement, options?: RenderOptions) {
  let result: RenderResult | undefined;

  await act(async () => {
    result = render(ui, options);
  });

  return result as RenderResult;
}

export async function rerenderWithAct(
  view: Pick<RenderResult, "rerender">,
  ui: ReactElement
) {
  await act(async () => {
    view.rerender(ui);
  });
}
