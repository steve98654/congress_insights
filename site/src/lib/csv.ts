const cell = (v: unknown) => {
  const s = v === null || v === undefined ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
export const csv = (rows: unknown[][]) => rows.map((r) => r.map(cell).join(',')).join('\n') + '\n';
