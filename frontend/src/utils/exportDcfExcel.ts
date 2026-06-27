import ExcelJS from "exceljs";
import type { DcfDraftData, DcfResult } from "../types";

const COL = (n: number) => String.fromCharCode(64 + n); // 1=A, 2=B, ...

function asSeries(value: number | number[], n: number): number[] {
  return Array.isArray(value) ? value : Array(n).fill(value);
}

/** Build an IB-style DCF workbook with live Excel formulas. */
export async function exportDcfToExcel(
  model: DcfResult,
  filename: string,
): Promise<void> {
  const { inputs, years } = model;
  const n = years.length;
  const firstYearCol = 3; // C
  const lastYearCol = firstYearCol + n - 1;
  const lastColLetter = COL(lastYearCol);

  const growths = asSeries(inputs.revenue_growth, n);
  const margins = asSeries(inputs.ebitda_margin, n);
  const taxes = asSeries(inputs.tax_rate, n);
  const capexPcts = asSeries(inputs.capex_pct, n);
  const nwcPcts = asSeries(inputs.nwc_pct, n);

  const wb = new ExcelJS.Workbook();
  wb.creator = "Financial Model Builder";
  const ws = wb.addWorksheet("DCF");

  ws.getColumn(1).width = 28;
  ws.getColumn(2).width = 14;
  for (let c = firstYearCol; c <= lastYearCol; c++) ws.getColumn(c).width = 12;

  const title = model.company_name
    ? `DCF — ${model.company_name}`
    : "DCF Valuation";
  ws.mergeCells(1, 1, 1, lastYearCol);
  ws.getCell(1, 1).value = title;
  ws.getCell(1, 1).font = { bold: true, size: 14 };

  // Assumptions (blue-style inputs)
  const assumptions: [string, number, string][] = [
    ["WACC", inputs.wacc, "0.0%"],
    ["Terminal Growth", inputs.terminal_growth, "0.0%"],
    ["Base Revenue ($M)", inputs.base_revenue, "#,##0.0"],
  ];
  ws.getCell(3, 1).value = "Assumptions";
  ws.getCell(3, 1).font = { bold: true };
  assumptions.forEach(([label, val, fmt], i) => {
    const r = 4 + i;
    ws.getCell(r, 1).value = label;
    ws.getCell(r, 2).value = val;
    ws.getCell(r, 2).numFmt = fmt;
    ws.getCell(r, 2).font = { color: { argb: "FF0000FF" } };
  });

  const waccRef = "$B$4";
  const termGRef = "$B$5";
  const baseRevRef = "$B$6";

  const headerRow = 8;
  ws.getCell(headerRow, 1).value = "($M)";
  ws.getCell(headerRow, 1).font = { bold: true };
  for (let i = 0; i < n; i++) {
    const col = firstYearCol + i;
    const cell = ws.getCell(headerRow, col);
    cell.value = `Year ${i + 1}`;
    cell.font = { bold: true };
    cell.alignment = { horizontal: "right" };
  }

  const growthRow = 9;
  ws.getCell(growthRow, 1).value = "Revenue Growth";
  for (let i = 0; i < n; i++) {
    const col = firstYearCol + i;
    ws.getCell(growthRow, col).value = growths[i];
    ws.getCell(growthRow, col).numFmt = "0.0%";
    ws.getCell(growthRow, col).font = { color: { argb: "FF0000FF" } };
  }

  const marginRow = 10;
  ws.getCell(marginRow, 1).value = "EBITDA Margin";
  for (let i = 0; i < n; i++) {
    ws.getCell(marginRow, firstYearCol + i).value = margins[i];
    ws.getCell(marginRow, firstYearCol + i).numFmt = "0.0%";
    ws.getCell(marginRow, firstYearCol + i).font = { color: { argb: "FF0000FF" } };
  }

  const taxInputRow = 11;
  ws.getCell(taxInputRow, 1).value = "Tax Rate";
  for (let i = 0; i < n; i++) {
    ws.getCell(taxInputRow, firstYearCol + i).value = taxes[i];
    ws.getCell(taxInputRow, firstYearCol + i).numFmt = "0.0%";
    ws.getCell(taxInputRow, firstYearCol + i).font = { color: { argb: "FF0000FF" } };
  }

  const capexInputRow = 12;
  ws.getCell(capexInputRow, 1).value = "CapEx % Rev";
  for (let i = 0; i < n; i++) {
    ws.getCell(capexInputRow, firstYearCol + i).value = capexPcts[i];
    ws.getCell(capexInputRow, firstYearCol + i).numFmt = "0.0%";
    ws.getCell(capexInputRow, firstYearCol + i).font = { color: { argb: "FF0000FF" } };
  }

  const nwcInputRow = 13;
  ws.getCell(nwcInputRow, 1).value = "ΔNWC % ΔRev";
  for (let i = 0; i < n; i++) {
    ws.getCell(nwcInputRow, firstYearCol + i).value = nwcPcts[i];
    ws.getCell(nwcInputRow, firstYearCol + i).numFmt = "0.0%";
    ws.getCell(nwcInputRow, firstYearCol + i).font = { color: { argb: "FF0000FF" } };
  }

  const revRow = 14;
  ws.getCell(revRow, 1).value = "Revenue";
  ws.getCell(revRow, 1).font = { bold: true };
  for (let i = 0; i < n; i++) {
    const col = firstYearCol + i;
    const colL = COL(col);
    const cell = ws.getCell(revRow, col);
    if (i === 0) {
      cell.value = {
        formula: `${baseRevRef}*(1+${colL}$${growthRow})`,
      };
    } else {
      const prevCol = COL(col - 1);
      cell.value = {
        formula: `${prevCol}${revRow}*(1+${colL}$${growthRow})`,
      };
    }
    cell.numFmt = '#,##0.0';
  }

  const ebitdaRow = 15;
  ws.getCell(ebitdaRow, 1).value = "EBITDA";
  ws.getCell(ebitdaRow, 1).font = { bold: true };
  for (let i = 0; i < n; i++) {
    const col = firstYearCol + i;
    const colL = COL(col);
    const cell = ws.getCell(ebitdaRow, col);
    cell.value = { formula: `${colL}${revRow}*${colL}$${marginRow}` };
    cell.numFmt = '#,##0.0';
  }

  const taxRow = 16;
  ws.getCell(taxRow, 1).value = "Less: Taxes";
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(taxRow, firstYearCol + i).value = {
      formula: `${colL}${ebitdaRow}*${colL}$${taxInputRow}`,
    };
    ws.getCell(taxRow, firstYearCol + i).numFmt = '#,##0.0';
  }

  const nopatRow = 17;
  ws.getCell(nopatRow, 1).value = "NOPAT";
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(nopatRow, firstYearCol + i).value = {
      formula: `${colL}${ebitdaRow}-${colL}${taxRow}`,
    };
    ws.getCell(nopatRow, firstYearCol + i).numFmt = '#,##0.0';
  }

  const capexRow = 18;
  ws.getCell(capexRow, 1).value = "Less: CapEx";
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(capexRow, firstYearCol + i).value = {
      formula: `${colL}${revRow}*${colL}$${capexInputRow}`,
    };
    ws.getCell(capexRow, firstYearCol + i).numFmt = '#,##0.0';
  }

  const nwcRow = 19;
  ws.getCell(nwcRow, 1).value = "Less: Δ NWC";
  for (let i = 0; i < n; i++) {
    const col = firstYearCol + i;
    const colL = COL(col);
    const cell = ws.getCell(nwcRow, col);
    if (i === 0) {
      cell.value = {
        formula: `(${colL}${revRow}-${baseRevRef})*${colL}$${nwcInputRow}`,
      };
    } else {
      const prevCol = COL(col - 1);
      cell.value = {
        formula: `(${colL}${revRow}-${prevCol}${revRow})*${colL}$${nwcInputRow}`,
      };
    }
    cell.numFmt = '#,##0.0';
  }

  const fcfRow = 20;
  ws.getCell(fcfRow, 1).value = "Unlevered FCF";
  ws.getCell(fcfRow, 1).font = { bold: true };
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(fcfRow, firstYearCol + i).value = {
      formula: `${colL}${nopatRow}-${colL}${capexRow}-${colL}${nwcRow}`,
    };
    ws.getCell(fcfRow, firstYearCol + i).numFmt = '#,##0.0';
    ws.getCell(fcfRow, firstYearCol + i).font = { bold: true };
  }

  const dfRow = 21;
  ws.getCell(dfRow, 1).value = "Discount Factor";
  for (let i = 0; i < n; i++) {
    ws.getCell(dfRow, firstYearCol + i).value = {
      formula: `1/(1+${waccRef})^${i + 1}`,
    };
    ws.getCell(dfRow, firstYearCol + i).numFmt = "0.000";
  }

  const pvRow = 22;
  ws.getCell(pvRow, 1).value = "PV of UFCF";
  ws.getCell(pvRow, 1).font = { bold: true };
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(pvRow, firstYearCol + i).value = {
      formula: `${colL}${fcfRow}*${colL}${dfRow}`,
    };
    ws.getCell(pvRow, firstYearCol + i).numFmt = '#,##0.0';
  }

  const sumPvRef = `${COL(firstYearCol)}${pvRow}:${lastColLetter}${pvRow}`;
  const lastFcfRef = `${lastColLetter}${fcfRow}`;

  const summaryStart = 24;
  ws.getCell(summaryStart, 1).value = "Valuation Summary";
  ws.getCell(summaryStart, 1).font = { bold: true };

  ws.getCell(summaryStart + 1, 1).value = "PV of Explicit Period";
  ws.getCell(summaryStart + 1, 2).value = { formula: `SUM(${sumPvRef})` };
  ws.getCell(summaryStart + 1, 2).numFmt = '#,##0.0';

  ws.getCell(summaryStart + 2, 1).value = "Terminal Value (undiscounted)";
  ws.getCell(summaryStart + 2, 2).value = {
    formula: `${lastFcfRef}*(1+${termGRef})/(${waccRef}-${termGRef})`,
  };
  ws.getCell(summaryStart + 2, 2).numFmt = '#,##0.0';

  ws.getCell(summaryStart + 3, 1).value = "PV of Terminal Value";
  ws.getCell(summaryStart + 3, 2).value = {
    formula: `B${summaryStart + 2}/(1+${waccRef})^${n}`,
  };
  ws.getCell(summaryStart + 3, 2).numFmt = '#,##0.0';

  ws.getCell(summaryStart + 4, 1).value = "Enterprise Value";
  ws.getCell(summaryStart + 4, 1).font = { bold: true };
  ws.getCell(summaryStart + 4, 2).value = {
    formula: `B${summaryStart + 1}+B${summaryStart + 3}`,
  };
  ws.getCell(summaryStart + 4, 2).numFmt = '#,##0.0';
  ws.getCell(summaryStart + 4, 2).font = { bold: true };

  let row = summaryStart + 5;
  if (inputs.net_debt != null) {
    ws.getCell(row, 1).value = "Less: Net Debt";
    ws.getCell(row, 2).value = inputs.net_debt;
    ws.getCell(row, 2).numFmt = '#,##0.0';
    ws.getCell(row, 2).font = { color: { argb: "FF0000FF" } };
    row += 1;
    ws.getCell(row, 1).value = "Equity Value";
    ws.getCell(row, 1).font = { bold: true };
    ws.getCell(row, 2).value = {
      formula: `B${summaryStart + 4}-B${row - 1}`,
    };
    ws.getCell(row, 2).numFmt = '#,##0.0';
    ws.getCell(row, 2).font = { bold: true };
    row += 1;
  }

  if (inputs.shares_outstanding != null && inputs.net_debt != null) {
    ws.getCell(row, 1).value = "Shares Outstanding (M)";
    ws.getCell(row, 2).value = inputs.shares_outstanding;
    ws.getCell(row, 2).font = { color: { argb: "FF0000FF" } };
    row += 1;
    ws.getCell(row, 1).value = "Price per Share";
    ws.getCell(row, 1).font = { bold: true };
    ws.getCell(row, 2).value = {
      formula: `B${row - 2}/B${row - 1}`,
    };
    ws.getCell(row, 2).numFmt = '$#,##0.00';
    ws.getCell(row, 2).font = { bold: true };
  }

  const buffer = await wb.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".xlsx") ? filename : `${filename}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

/** Template workbook: empty input cells + formulas; optional 5Y Reference sheet. */
export async function exportDcfTemplateExcel(
  draft: DcfDraftData,
  filename: string,
): Promise<void> {
  const n = draft.projection_years;
  const firstYearCol = 3;
  const lastYearCol = firstYearCol + n - 1;
  const lastColLetter = COL(lastYearCol);

  const wb = new ExcelJS.Workbook();
  wb.creator = "Financial Model Builder";
  const ws = wb.addWorksheet("DCF");

  ws.getColumn(1).width = 28;
  ws.getColumn(2).width = 14;
  for (let c = firstYearCol; c <= lastYearCol; c++) ws.getColumn(c).width = 12;

  const title = `${draft.ticker} DCF — ${n}-year forecast (template)`;
  ws.mergeCells(1, 1, 1, lastYearCol);
  ws.getCell(1, 1).value = title;
  ws.getCell(1, 1).font = { bold: true, size: 14 };

  const assumptionLabels = [
    "WACC",
    "Terminal Growth",
    "Tax Rate (default)",
    "EBITDA Margin (default)",
    "CapEx % Revenue (default)",
    "ΔNWC % Revenue Growth (default)",
    "Base Revenue ($M)",
  ];
  ws.getCell(3, 1).value = "Assumptions";
  ws.getCell(3, 1).font = { bold: true };
  assumptionLabels.forEach((label, i) => {
    const r = 4 + i;
    ws.getCell(r, 1).value = label;
    ws.getCell(r, 2).font = { color: { argb: "FF0000FF" } };
  });

  const waccRef = "$B$4";
  const termGRef = "$B$5";
  const baseRevRef = "$B$10";

  const headerRow = 13;
  ws.getCell(headerRow, 1).value = "($M)";
  for (let i = 0; i < n; i++) {
    ws.getCell(headerRow, firstYearCol + i).value = `Year ${i + 1}`;
  }

  const growthRow = 14;
  ws.getCell(growthRow, 1).value = "Revenue Growth";
  for (let i = 0; i < n; i++) {
    ws.getCell(growthRow, firstYearCol + i).font = { color: { argb: "FF0000FF" } };
    ws.getCell(growthRow, firstYearCol + i).numFmt = "0.0%";
  }

  const marginRow = 15;
  ws.getCell(marginRow, 1).value = "EBITDA Margin";
  for (let i = 0; i < n; i++) {
    ws.getCell(marginRow, firstYearCol + i).font = { color: { argb: "FF0000FF" } };
    ws.getCell(marginRow, firstYearCol + i).numFmt = "0.0%";
  }

  const taxRowPerYear = 16;
  ws.getCell(taxRowPerYear, 1).value = "Tax Rate";
  for (let i = 0; i < n; i++) {
    ws.getCell(taxRowPerYear, firstYearCol + i).font = { color: { argb: "FF0000FF" } };
    ws.getCell(taxRowPerYear, firstYearCol + i).numFmt = "0.0%";
  }

  const capexRowInput = 17;
  ws.getCell(capexRowInput, 1).value = "CapEx % Rev";
  for (let i = 0; i < n; i++) {
    ws.getCell(capexRowInput, firstYearCol + i).font = { color: { argb: "FF0000FF" } };
    ws.getCell(capexRowInput, firstYearCol + i).numFmt = "0.0%";
  }

  const nwcRowInput = 18;
  ws.getCell(nwcRowInput, 1).value = "ΔNWC % ΔRev";
  for (let i = 0; i < n; i++) {
    ws.getCell(nwcRowInput, firstYearCol + i).font = { color: { argb: "FF0000FF" } };
    ws.getCell(nwcRowInput, firstYearCol + i).numFmt = "0.0%";
  }

  const revRow = 19;
  ws.getCell(revRow, 1).value = "Revenue";
  for (let i = 0; i < n; i++) {
    const col = firstYearCol + i;
    const colL = COL(col);
    if (i === 0) {
      ws.getCell(revRow, col).value = {
        formula: `${baseRevRef}*(1+${colL}$${growthRow})`,
      };
    } else {
      ws.getCell(revRow, col).value = {
        formula: `${COL(col - 1)}${revRow}*(1+${colL}$${growthRow})`,
      };
    }
    ws.getCell(revRow, col).numFmt = "#,##0.0";
  }

  const ebitdaRow = 20;
  ws.getCell(ebitdaRow, 1).value = "EBITDA";
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(ebitdaRow, firstYearCol + i).value = {
      formula: `${colL}${revRow}*${colL}$${marginRow}`,
    };
    ws.getCell(ebitdaRow, firstYearCol + i).numFmt = "#,##0.0";
  }

  const taxRow = 21;
  ws.getCell(taxRow, 1).value = "Less: Taxes";
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(taxRow, firstYearCol + i).value = {
      formula: `${colL}${ebitdaRow}*${colL}$${taxRowPerYear}`,
    };
    ws.getCell(taxRow, firstYearCol + i).numFmt = "#,##0.0";
  }

  const nopatRow = 22;
  ws.getCell(nopatRow, 1).value = "NOPAT";
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(nopatRow, firstYearCol + i).value = {
      formula: `${colL}${ebitdaRow}-${colL}${taxRow}`,
    };
    ws.getCell(nopatRow, firstYearCol + i).numFmt = "#,##0.0";
  }

  const capexRow = 23;
  ws.getCell(capexRow, 1).value = "Less: CapEx";
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(capexRow, firstYearCol + i).value = {
      formula: `${colL}${revRow}*${colL}$${capexRowInput}`,
    };
    ws.getCell(capexRow, firstYearCol + i).numFmt = "#,##0.0";
  }

  const nwcRow = 24;
  ws.getCell(nwcRow, 1).value = "Less: Δ NWC";
  for (let i = 0; i < n; i++) {
    const col = firstYearCol + i;
    const colL = COL(col);
    if (i === 0) {
      ws.getCell(nwcRow, col).value = {
        formula: `(${colL}${revRow}-${baseRevRef})*${colL}$${nwcRowInput}`,
      };
    } else {
      ws.getCell(nwcRow, col).value = {
        formula: `(${colL}${revRow}-${COL(col - 1)}${revRow})*${colL}$${nwcRowInput}`,
      };
    }
    ws.getCell(nwcRow, col).numFmt = "#,##0.0";
  }

  const fcfRow = 25;
  ws.getCell(fcfRow, 1).value = "Unlevered FCF";
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(fcfRow, firstYearCol + i).value = {
      formula: `${colL}${nopatRow}-${colL}${capexRow}-${colL}${nwcRow}`,
    };
    ws.getCell(fcfRow, firstYearCol + i).numFmt = "#,##0.0";
  }

  const dfRow = 26;
  ws.getCell(dfRow, 1).value = "Discount Factor";
  for (let i = 0; i < n; i++) {
    ws.getCell(dfRow, firstYearCol + i).value = {
      formula: `1/(1+${waccRef})^${i + 1}`,
    };
  }

  const pvRow = 27;
  ws.getCell(pvRow, 1).value = "PV of UFCF";
  for (let i = 0; i < n; i++) {
    const colL = COL(firstYearCol + i);
    ws.getCell(pvRow, firstYearCol + i).value = {
      formula: `${colL}${fcfRow}*${colL}${dfRow}`,
    };
    ws.getCell(pvRow, firstYearCol + i).numFmt = "#,##0.0";
  }

  const sumPvRef = `${COL(firstYearCol)}${pvRow}:${lastColLetter}${pvRow}`;
  const lastFcfRef = `${lastColLetter}${fcfRow}`;
  const summaryStart = 29;
  ws.getCell(summaryStart + 1, 1).value = "PV of Explicit Period";
  ws.getCell(summaryStart + 1, 2).value = { formula: `SUM(${sumPvRef})` };
  ws.getCell(summaryStart + 2, 1).value = "Terminal Value";
  ws.getCell(summaryStart + 2, 2).value = {
    formula: `${lastFcfRef}*(1+${termGRef})/(${waccRef}-${termGRef})`,
  };
  ws.getCell(summaryStart + 3, 1).value = "PV of Terminal Value";
  ws.getCell(summaryStart + 3, 2).value = {
    formula: `B${summaryStart + 2}/(1+${waccRef})^${n}`,
  };
  ws.getCell(summaryStart + 4, 1).value = "Enterprise Value";
  ws.getCell(summaryStart + 4, 2).value = {
    formula: `B${summaryStart + 1}+B${summaryStart + 3}`,
  };

  const ref = draft.reference_history;
  if (ref.fiscal_years.length > 0) {
    const refWs = wb.addWorksheet("Reference");
    refWs.getCell(1, 1).value = `${ref.ticker} — 5-year SEC reference (historical)`;
    refWs.getCell(2, 1).value = "Metric";
    ref.fiscal_years.forEach((fy, i) => {
      refWs.getCell(2, 2 + i).value = `FY${fy}`;
    });
    ref.rows.forEach((row, ri) => {
      const r = 3 + ri;
      refWs.getCell(r, 1).value = row.label;
      row.values.forEach((val, ci) => {
        if (val != null) {
          refWs.getCell(r, 2 + ci).value = val;
        }
      });
    });
  }

  const buffer = await wb.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".xlsx") ? filename : `${filename}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}
