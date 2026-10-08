interface Props {
  page: number;
  pages: number;
  hasMore: boolean;
  onPage: (page: number) => void;
}

// First, last, and two either side of the current page; gaps shown as "…".
function window_(page: number, pages: number): (number | "gap")[] {
  const keep = new Set([1, pages, page - 2, page - 1, page, page + 1, page + 2]);
  const out: (number | "gap")[] = [];
  for (let n = 1; n <= pages; n++) {
    if (keep.has(n)) out.push(n);
    else if (out[out.length - 1] !== "gap") out.push("gap");
  }
  return out;
}

export function Pager({ page, pages, hasMore, onPage }: Props) {
  if (pages <= 1 && !hasMore) return null;
  return (
    <nav className="pager" aria-label="Pages">
      <button className="pager__step" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        ← Previous
      </button>
      <ol className="pager__pages">
        {window_(page, pages).map((n, i) =>
          n === "gap" ? (
            <li key={`gap${i}`} className="pager__gap" aria-hidden="true">…</li>
          ) : (
            <li key={n}>
              <button className="pager__page" aria-current={n === page ? "page" : undefined} onClick={() => onPage(n)}>
                {n}
              </button>
            </li>
          ),
        )}
      </ol>
      <button className="pager__step" disabled={!hasMore} onClick={() => onPage(page + 1)}>
        Next →
      </button>
    </nav>
  );
}
