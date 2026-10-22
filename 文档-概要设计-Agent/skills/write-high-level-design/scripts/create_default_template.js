const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  Header,
  HeadingLevel,
  Packer,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = require("docx");

const outputPath = process.argv[2];
if (!outputPath) {
  throw new Error("必须提供输出 DOCX 路径");
}

const pageWidth = 11906;
const pageHeight = 16838;
const pageMargin = 1440;
const contentWidth = pageWidth - pageMargin * 2;
const border = { style: BorderStyle.SINGLE, size: 1, color: "B8C2CC" };
const borders = { top: border, bottom: border, left: border, right: border };
const columnWidths = [2200, contentWidth - 2200];

function cell(text, width, header = false) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: header ? { fill: "D9EAF7", type: ShadingType.CLEAR } : undefined,
    margins: { top: 100, bottom: 100, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text, bold: header, font: "Arial Unicode MS", size: 21 })] })],
  });
}

const document = new Document({
  styles: {
    default: {
      document: { run: { font: "Arial Unicode MS", size: 21, color: "111111" }, paragraph: { spacing: { line: 360, after: 120 } } },
    },
    paragraphStyles: [
      {
        id: "Title",
        name: "Title",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Arial Unicode MS", size: 44, bold: true, color: "111111" },
        paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 1600, after: 720 } },
      },
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Arial Unicode MS", size: 32, bold: true, color: "1F4E79" },
        paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Arial Unicode MS", size: 28, bold: true, color: "243746" },
        paragraph: { spacing: { before: 280, after: 180 }, outlineLevel: 1 },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Arial Unicode MS", size: 24, bold: true, color: "243746" },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 2 },
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: pageWidth, height: pageHeight },
          margin: { top: pageMargin, right: pageMargin, bottom: pageMargin, left: pageMargin },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F4E79", space: 1 } },
              children: [new TextRun({ text: "概要设计说明书", font: "Arial Unicode MS", size: 18, color: "5B6573" })],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "第 ", font: "Arial Unicode MS", size: 18 }),
                new TextRun({ children: [PageNumber.CURRENT], font: "Arial Unicode MS", size: 18 }),
                new TextRun({ text: " 页", font: "Arial Unicode MS", size: 18 }),
              ],
            }),
          ],
        }),
      },
      children: [
        new Paragraph({ style: "Title", children: [new TextRun("概要设计说明书")] }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "默认参考模板", font: "Arial Unicode MS", size: 26 })] }),
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("1 一级标题样式")] }),
        new Paragraph({ children: [new TextRun("这是用于定义正文、标题、页眉页脚和表格样式的参考文档。正式内容由 Agent 生成。")] }),
        new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("1.1 二级标题样式")] }),
        new Table({
          width: { size: contentWidth, type: WidthType.DXA },
          columnWidths,
          rows: [
            new TableRow({ children: [cell("项目", columnWidths[0], true), cell("内容", columnWidths[1], true)] }),
            new TableRow({ children: [cell("示例", columnWidths[0]), cell("表格样式", columnWidths[1])] }),
          ],
        }),
      ],
    },
  ],
});

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
Packer.toBuffer(document).then((buffer) => fs.writeFileSync(outputPath, buffer));
