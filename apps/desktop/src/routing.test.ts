import {describe, expect, it} from "vitest";

import {routeFromHash} from "./routing";

describe("routeFromHash encoding", () => {
  const id = "user.e2e测试";
  const encoded = encodeURIComponent(id);

  it("decodes percent-encoded method ids in the hash", () => {
    expect(routeFromHash(`#/methods/${encoded}`)).toBe(`#/methods/${id}`);
  });

  it("leaves already-decoded method ids unchanged", () => {
    expect(routeFromHash(`#/methods/${id}`)).toBe(`#/methods/${id}`);
  });
});
