export function detectKind(filename) {
  const n = String(filename).toLowerCase();
  if (n.endsWith(".pkg")) return "pkg";
  if (n.endsWith(".tex")) return "tex";
  if (n.endsWith(".mpkg")) return "mpkg";
  return null;
}
