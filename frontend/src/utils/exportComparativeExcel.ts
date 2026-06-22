import ExcelJS from "exceljs";
import type { ComparativeReport } from "../types";
import { COMPARATIVE_ROWS } from "../components/ComparativeTable";

export async function exportComparativeToExcel(
  report: ComparativeReport,
  filename: string,
): Promise<void> {
  const wb = new ExcelJS.Workbook();
  wb.creator = "Financial Model Builder";
  const ws = wb.addWorksheet("Comparative");

  ws.getColumn(1).width = 22;
  const companies = report.companies;
  companies.forEach((_, i) => {
    ws.getColumn(i + 2).width = 16;
  });

  ws.getCell(1, 1).value = `Peer comparison — FY${report.fiscal_year_used}`;
  ws.getCell(1, 1).font = { bold: true, size: 14 };

  const headerRow = 3;
  ws.getCell(headerRow, 1).value = "Metric";
  companies.forEach((c, i) => {
    ws.getCell(headerRow, i + 2).value = c.is_target
      ? `${c.company_name || c.ticker} (Target)`
      : c.company_name || c.ticker;
    ws.getCell(headerRow, i + 2).font = { bold: true };
  });

  let row = headerRow + 1;
  for (const def of COMPARATIVE_ROWS) {
    ws.getCell(row, 1).value = def.label;
    companies.forEach((c, i) => {
      ws.getCell(row, i + 2).value = def.get(c);
    });
    row += 1;
  }

  const buf = await wb.xlsx.writeBuffer();
  const blob = new Blob([buf], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename.replace(/[^a-z0-9_-]+/gi, "_")}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

/** Row labels exported for tests */
export function comparativeExportRowLabels(_report: ComparativeReport): string[] {
  return COMPARATIVE_ROWS.map((r) => r.label);
}

export function comparativeExportCompanyCount(report: ComparativeReport): number {
  return report.companies.length;
}
