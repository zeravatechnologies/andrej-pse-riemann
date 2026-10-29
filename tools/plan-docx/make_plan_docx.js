// Generates "PSE Riemann — PLAN.docx" in the repo root from docs/PLAN.md, with
// the round-3 progress table from docs/WORKLOG.md on top. docs/PLAN.md stays the
// source of truth; run this after every plan change:
//     node tools/plan-docx/make_plan_docx.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, AlignmentType, Footer, PageNumber,
  TableOfContents, LevelFormat, ImageRun,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const PLAN = fs.readFileSync(path.join(ROOT, "docs", "PLAN.md"), "utf8");
const WORKLOG = fs.readFileSync(path.join(ROOT, "docs", "WORKLOG.md"), "utf8");
const OUT = path.join(ROOT, "PSE Riemann — PLAN.docx");

const PAGE_W = 11906, MARGIN = 1134;               // A4, 2 cm margins
const CONTENT_W = PAGE_W - 2 * MARGIN;
const ACCENT = "B07A1E", DARK = "1F2430", MUTED = "5B6270", ROW_ALT = "F4F1EA";

// ---------------------------------------------------------------- inline md
function runs(text, base = {}) {
  const out = [];
  // links → their text
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1");
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", color: "6B4A12", ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out.length ? out : [new TextRun({ text: "", ...base })];
}

// ---------------------------------------------------------------- tables
const border = { style: BorderStyle.SINGLE, size: 4, color: "D9D4C7" };
const borders = { top: border, bottom: border, left: border, right: border };

function table(rows, weights) {
  const ncol = rows[0].length;
  weights = weights || Array(ncol).fill(1);
  const tot = weights.reduce((a, b) => a + b, 0);
  const widths = weights.map((w) => Math.floor((CONTENT_W * w) / tot));
  widths[ncol - 1] += CONTENT_W - widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map((cells, i) => new TableRow({
      tableHeader: i === 0,
      children: cells.map((c, j) => new TableCell({
        borders,
        width: { size: widths[j], type: WidthType.DXA },
        shading: i === 0 ? { fill: DARK, type: ShadingType.CLEAR, color: "auto" }
          : (i % 2 === 0 ? { fill: ROW_ALT, type: ShadingType.CLEAR, color: "auto" } : undefined),
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({
          spacing: { after: 0 },
          children: runs(c, i === 0 ? { bold: true, color: "FFFFFF", size: 19 } : { size: 19 }),
        })],
      })),
    })),
  });
}

function parseTable(lines) {
  return lines
    .filter((l) => !/^\|\s*-{2,}/.test(l.replace(/:/g, "")))
    .map((l) => l.trim().replace(/^\||\|$/g, "").split(/(?<!\\)\|/)
      .map((c) => c.trim().replace(/\\\|/g, "|")));
}

// ---------------------------------------------------------------- blocks
function para(text, opts = {}) {
  return new Paragraph({ spacing: { after: 100 }, ...opts, children: runs(text, opts.run || {}) });
}

function convert(md) {
  const out = [];
  const lines = md.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) continue;
    const im = line.trim().match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    if (im) {                                         // a picture (PNG), scaled to the page
      const base = global.__MD_DIR || ROOT;
      const f = path.resolve(base, im[2]);
      if (fs.existsSync(f)) {
        const buf = fs.readFileSync(f);
        const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
        const maxW = Math.floor(CONTENT_W / 15);      // twips → px at 96 dpi
        const sw = Math.min(maxW, w), sh = Math.round(h * sw / w);
        out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
          children: [new ImageRun({ type: "png", data: buf, transformation: { width: sw, height: sh } })] }));
        if (im[1]) out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
          children: [new TextRun({ text: im[1], italics: true, size: 18, color: "666666" })] }));
      }
      continue;
    }
    if (/^```/.test(line.trim())) {                  // fenced code: grey monospace box
      i++;
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        out.push(new Paragraph({ spacing: { after: 0 }, indent: { left: 360 },
          shading: { type: ShadingType.CLEAR, fill: "F1EEE6", color: "auto" },
          children: [new TextRun({ text: lines[i] || " ", font: "Consolas", size: 20, color: "3A2A06" })] }));
        i++;
      }
      out.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
      continue;
    }
    if (/^---+$/.test(line.trim())) {
      out.push(new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT, space: 1 } }, spacing: { after: 160 }, children: [] }));
      continue;
    }
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
      const lvl = [HeadingLevel.HEADING_1, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][m[1].length - 1];
      out.push(new Paragraph({ heading: lvl, children: runs(m[2]) }));
      continue;
    }
    if (line.startsWith("|")) {
      const block = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) block.push(lines[i++]);
      i--;
      const rows = parseTable(block);
      const w = rows[0].length === 2 ? [1, 3] : rows[0].length === 3 ? [0.5, 1.6, 5]
              : rows[0].length === 4 ? [0.6, 1.4, 6, 0.9]
              : rows[0].length === 5 ? [1.1, 1.6, 0.9, 1.3, 4] : undefined;
      out.push(table(rows, w));
      out.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
      continue;
    }
    if ((m = line.match(/^>\s?(.*)$/))) {
      out.push(para(m[1], { indent: { left: 400 }, run: { italics: true, color: MUTED },
        border: { left: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 8 } } }));
      continue;
    }
    const indent = raw.match(/^(\s*)/)[1].length;
    if ((m = line.match(/^\s*(\d+)\.\s+(.*)$/))) {
      // keep the plan's own numbers (they are referenced everywhere)
      const left = 460 + Math.floor(indent / 3) * 360;
      out.push(new Paragraph({
        spacing: { after: 80 }, indent: { left, hanging: 460 },
        children: [new TextRun({ text: `${m[1]}.\t`, bold: indent === 0, color: indent === 0 ? ACCENT : DARK }), ...runs(m[2])],
        tabStops: [{ type: "left", position: left }],
      }));
      continue;
    }
    if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
      const level = Math.min(2, Math.floor(indent / 4));
      out.push(new Paragraph({ numbering: { reference: "bul", level }, spacing: { after: 60 }, children: runs(m[1]) }));
      continue;
    }
    // indented continuation under a numbered item
    out.push(para(line.trim(), { indent: { left: indent > 0 ? 460 + Math.floor(indent / 4) * 360 : 0 } }));
  }
  return out;
}

// ---------------------------------------------------------------- status
function progressTable() {
  const a = WORKLOG.indexOf("## Runda 3 — napredak");
  if (a < 0) return [];
  const seg = WORKLOG.slice(a).split("\n");
  const rows = [];
  for (const l of seg.slice(1)) {
    if (l.startsWith("|")) rows.push(l);
    else if (rows.length && !l.trim()) break;
  }
  const out = [];
  if (rows.length) {
    const parsed = parseTable(rows);
    out.push(table(parsed, [1.1, 1.6, 0.9, 1.3, 4]));
  }
  const nxt = WORKLOG.match(/\*\*Sljedeće:\*\*[^\n]*/);
  const rem = WORKLOG.match(/\*\*Preostalo:\*\*[^\n]*/);
  out.push(new Paragraph({ spacing: { before: 160, after: 60 }, children: [] }));
  if (nxt) out.push(para(nxt[0]));
  if (rem) out.push(para(rem[0]));
  return out;
}

// ---------------------------------------------------------------- document
const today = new Date().toISOString().slice(0, 10);
// any Markdown file → its own docx:  node make_plan_docx.js --md docs/OSTALO.md --out "X.docx"
const argv = process.argv.slice(2);
const ARG_MD = argv.includes("--md") ? argv[argv.indexOf("--md") + 1] : null;
const ARG_OUT = argv.includes("--out") ? argv[argv.indexOf("--out") + 1] : null;
if (ARG_MD) global.__MD_DIR = path.dirname(path.resolve(ROOT, ARG_MD));
const children = ARG_MD ? convert(fs.readFileSync(path.resolve(ROOT, ARG_MD), "utf8")) : [
  new Paragraph({ spacing: { before: 1200, after: 120 }, children: [new TextRun({ text: "PSE Riemann", bold: true, size: 56, color: DARK })] }),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Plan rada — runda 2 i runda 3", size: 32, color: ACCENT })] }),
  new Paragraph({ spacing: { after: 600 }, children: [new TextRun({ text: `Stanje na dan ${today} · izvor: docs/PLAN.md i docs/WORKLOG.md (GitHub andrejristic/pse-riemann)`, size: 20, color: MUTED })] }),
  new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Stanje runde 3")] }),
  ...progressTable(),
  new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun("Sadržaj")] }),
  new TableOfContents("Sadržaj", { hyperlink: true, headingStyleRange: "1-3" }),
  new Paragraph({ pageBreakBefore: true, children: [] }),
  ...convert(PLAN),
];

const doc = new Document({
  creator: "Andrej Ristić",
  title: "PSE Riemann — plan rada",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: "Calibri", size: 21, color: "222222" } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, color: DARK }, paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, color: ACCENT }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, color: DARK }, paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [{ reference: "bul", levels: [0, 1, 2].map((lvl) => ({
    level: lvl, format: LevelFormat.BULLET, text: ["•", "◦", "▪"][lvl], alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 460 + lvl * 360 + 360, hanging: 300 } } } })) }] },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      new TextRun({ text: (ARG_MD ? (fs.readFileSync(path.resolve(ROOT, ARG_MD), "utf8").match(/^#\s+(.*)$/m) || [, "PSE Riemann"])[1].replace(/[*`]/g, "")
                           : "PSE Riemann — plan") + " · strana ", size: 16, color: MUTED }),
      new TextRun({ children: [PageNumber.CURRENT], size: 16, color: MUTED })] })] }) },
    children,
  }],
});

const OUTFILE = ARG_OUT ? path.resolve(ROOT, ARG_OUT) : OUT;
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUTFILE, buf); console.log("napisano:", OUTFILE); });
