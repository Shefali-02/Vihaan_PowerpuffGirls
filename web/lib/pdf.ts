/* Purpose: Build a tiny local demo PDF so the public verifier can validate a downloaded pack. */

import type { PackResponse } from "@/lib/api/types";


function escapePdf(value: string) { return value.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)").replace(/[^\x20-\x7e]/g, "?"); }

export function createPackPdf(pack: PackResponse) {
  const lines = [
    "MUNSHI - ACME PVT LTD",
    "Independent demo investor pack",
    `Financial year: ${pack.report.fy}`,
    `Report hash: ${pack.hash}`,
    `Anchor transaction: ${pack.anchorTx}`,
    `Revenue, six months: INR ${pack.report.months.reduce((sum, month) => sum + month.revenue, 0)}`,
    `Expenses, six months: INR ${pack.report.months.reduce((sum, month) => sum + month.expenses, 0)}`,
    `Net GST due: INR ${pack.report.gst.netDue}`,
    `Signed by: ${pack.signoffs.map((item) => `${item.name}, ${item.role}`).join("; ")}`,
    "Verify this report at the /verify page using the hash above.",
    "Independent hackathon project. Not affiliated with or endorsed by any government body.",
  ];
  const operations = ["BT /F1 16 Tf 52 780 Td", `(${escapePdf(lines[0])}) Tj`, "/F1 10 Tf"].concat(lines.slice(1).flatMap((line) => ["0 -28 Td", `(${escapePdf(line)}) Tj`])).join("\n");
  const stream = `${operations}\nET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${new TextEncoder().encode(stream).length} >>\nstream\n${stream}\nendstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(new TextEncoder().encode(pdf).length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xrefOffset = new TextEncoder().encode(pdf).length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;
  return new Blob([pdf], { type: "application/pdf" });
}

export function downloadPackPdf(pack: PackResponse) {
  const url = URL.createObjectURL(createPackPdf(pack));
  const link = document.createElement("a"); link.href = url; link.download = `acme-investor-pack-${pack.report.fy.replace(/\D/g, "")}.pdf`;
  document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
}
