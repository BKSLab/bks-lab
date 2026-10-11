import { cleanup } from "@testing-library/react";
import { afterEach, expect } from "vitest";
import * as matchers from "vitest-axe/matchers";
import "vitest-axe/extend-expect";

expect.extend(matchers);

// CodeMirror 6 measures the DOM through layout APIs jsdom does not implement;
// empty geometry stubs keep editor tests free of unrelated async errors.
const emptyDomRectList = {
  length: 0,
  item: () => null,
  [Symbol.iterator]: function* () { /* no rects */ },
} as unknown as DOMRectList;
if (typeof Range !== "undefined") {
  Range.prototype.getClientRects = () => emptyDomRectList;
  Range.prototype.getBoundingClientRect = () => ({ x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, toJSON: () => ({}) }) as DOMRect;
}

afterEach(() => {
  cleanup();
});
