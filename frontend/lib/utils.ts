export const errorMessage = (e: unknown): string =>
  e instanceof Error ? e.message : "An unexpected error occurred";

export const ago = (d: string) => {
  const normalized = d.endsWith("Z") || d.includes("+") ? d : d + "Z";
  const secs = Math.floor((Date.now() - new Date(normalized).getTime()) / 1000);
  if (secs < 0) return "just now";
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
};

export const shortPath = (filePath: string) =>
  filePath.split("/").slice(-2).join("/");
