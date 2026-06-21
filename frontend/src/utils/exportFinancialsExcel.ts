import ExcelJS from "exceljs";
import type { FinancialStatements } from "../types";

const STATEMENT_LABELS: Record<string, string> = {
  income: "Income Statement",
  balance: "Balance Sheet",
  cashflow: "Cash Flow",
};

export async function exportFinancialsToExcel(
  financials: FinancialStatements,
  filename: string,
): Promise<void> {
  const wb = new ExcelJS.Workbook();
  wb.creator = "Financial Model Builder";

  const scope = financials.fetch_scope ?? [
    "income",
    "balance",
    "cashflow",
  ];

  for (const key of scope) {
    const slice = financials.statements[key];
    if (!slice?.annual?.length) continue;

    const periods = slice.annual.slice(0, 5);
    const ws = wb.addWorksheet(STATEMENT_LABELS[key] ?? key);

    ws.getCell(1, 1).value = `${financials.entity_name} (${financials.ticker})`;
    ws.getCell(1, 1).font = { bold: true, size: 12 };
    ws.getCell(2, 1).value = STATEMENT_LABELS[key] ?? key;
    ws.getCell(2, 1).font = { bold: true };

    const headerRow = 4;
    ws.getCell(headerRow, 1).value = "Line Item";
    ws.getCell(headerRow, 1).font = { bold: true };
    periods.forEach((p, i) => {
      const cell = ws.getCell(headerRow, i + 2);
      cell.value = `FY${p.fiscal_year}`;
      cell.font = { bold: true };
      cell.alignment = { horizontal: "right" };
    });

    const rowKeys = periods[0].line_items.map((li) => li.key);
    rowKeys.forEach((rowKey, ri) => {
      const row = headerRow + 1 + ri;
      const label =
        periods[0].line_items.find((li) => li.key === rowKey)?.label ?? rowKey;
      ws.getCell(row, 1).value = label;
      periods.forEach((p, ci) => {
        const item = p.line_items.find((li) => li.key === rowKey);
        if (!item) return;
        const cell = ws.getCell(row, ci + 2);
        cell.value = item.value;
        cell.numFmt = item.unit === "USD/shares" ? "0.00" : "#,##0";
      });
    });

    ws.getColumn(1).width = 32;
    for (let c = 2; c <= periods.length + 1; c++) {
      ws.getColumn(c).width = 14;
    }
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
