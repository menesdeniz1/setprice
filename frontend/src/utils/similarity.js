/**
 * Bulanık (fuzzy) string benzerliği — normalize edilmiş Levenshtein oranı.
 * Backend'deki src/web_backend/similarity_utils.py'nin (difflib tabanlı)
 * frontend karşılığı; aynı fikir, farklı algoritma (dış bağımlılık yok).
 */
export function levenshteinDistance(a, b) {
  const m = a.length;
  const n = b.length;
  if (m === 0) return n;
  if (n === 0) return m;

  let prevRow = Array.from({ length: n + 1 }, (_, i) => i);
  for (let i = 1; i <= m; i++) {
    const currRow = [i];
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      currRow.push(Math.min(
        currRow[j - 1] + 1, // silme
        prevRow[j] + 1,     // ekleme
        prevRow[j - 1] + cost // değiştirme
      ));
    }
    prevRow = currRow;
  }
  return prevRow[n];
}

/**
 * 0-1 arası benzerlik oranı döner (1 = birebir aynı).
 */
export function stringSimilarity(a, b) {
  const normA = (a || '').trim().toLowerCase();
  const normB = (b || '').trim().toLowerCase();
  if (!normA && !normB) return 1;
  if (!normA || !normB) return 0;
  const maxLen = Math.max(normA.length, normB.length);
  return 1 - levenshteinDistance(normA, normB) / maxLen;
}
