"use strict";

function normalizeMargin(margin) {
  if (Array.isArray(margin)) return margin;
  const value = Number.isFinite(margin) ? margin : 0;
  return [value, value, value, value];
}

function textUnits(value) {
  return Array.from(String(value)).reduce((total, character) => {
    if (character === "\n") return total;
    if (/[\u2E80-\u9FFF\uF900-\uFAFF]/u.test(character)) return total + 1;
    if (/[A-Z0-9]/u.test(character)) return total + 0.62;
    if (/[a-z]/u.test(character)) return total + 0.52;
    if (/\s/u.test(character)) return total + 0.3;
    return total + 0.45;
  }, 0);
}

function createLayoutGuard({
  pptx,
  slideWidth = 13.333,
  slideHeight = 7.5,
  footerTop = 7.02,
  defaultTextOptions = {},
}) {
  const records = [];
  const estimatedOverflow = [];

  function record(page, kind, name, x, y, w, h) {
    records.push({ page, kind, name, x, y, w, h });
  }

  function estimateText(page, name, value, w, h, options) {
    const fontSize = options.fontSize || 12;
    const margins = normalizeMargin(options.margin);
    const availableWidth = Math.max(12, w * 72 - margins[1] - margins[3]);
    const availableHeight = Math.max(8, h * 72 - margins[0] - margins[2]);
    const lines = String(value).split("\n").reduce((total, line) => {
      return total + Math.max(1, Math.ceil((textUnits(line) * fontSize) / availableWidth));
    }, 0);
    const requiredHeight = lines * fontSize * 1.18;
    if (requiredHeight > availableHeight * 1.06) {
      estimatedOverflow.push({
        page,
        name,
        requiredHeightPt: Number(requiredHeight.toFixed(1)),
        availableHeightPt: Number(availableHeight.toFixed(1)),
      });
    }
  }

  function addShape(slide, page, type, x, y, w, h, options = {}, name = "shape") {
    record(page, "shape", name, x, y, w, h);
    slide.addShape(type, { x, y, w, h, ...options, objectName: `${page}-${name}` });
  }

  function addText(slide, page, value, x, y, w, h, options = {}, name = "text") {
    const textOptions = {
      x,
      y,
      w,
      h,
      fontSize: 12,
      margin: [2, 3, 2, 3],
      valign: "mid",
      fit: "shrink",
      ...defaultTextOptions,
      ...options,
      objectName: `${page}-${name}`,
    };
    record(page, "text", name, x, y, w, h);
    estimateText(page, name, value, w, h, textOptions);
    slide.addText(value, textOptions);
  }

  function addLine(slide, page, x, y, w, h, line, name = "line") {
    addShape(
      slide,
      page,
      pptx.ShapeType.line,
      x,
      y,
      w,
      h,
      { line: { ...line } },
      name,
    );
  }

  function buildReport(slideCount) {
    const outOfBounds = records.filter(({ x, y, w, h }) => {
      return x < -0.001
        || y < -0.001
        || x + w > slideWidth + 0.001
        || y + h > slideHeight + 0.001;
    });
    const footerCollisions = records.filter(({ kind, name, y, h }) => {
      return kind !== "shape"
        && !name.includes("footer")
        && y + h > footerTop;
    });
    return {
      status: outOfBounds.length === 0
        && footerCollisions.length === 0
        && estimatedOverflow.length === 0
        ? "passed"
        : "failed",
      canvas: { width: slideWidth, height: slideHeight },
      slideCount,
      objectCount: records.length,
      outOfBounds,
      footerCollisions,
      estimatedOverflow,
    };
  }

  return { addShape, addText, addLine, buildReport };
}

module.exports = { createLayoutGuard };
