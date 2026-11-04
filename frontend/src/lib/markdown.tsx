/* Minimal, safe Markdown renderer (headings, paragraphs, lists, bold, links). No raw HTML is ever rendered. */
import { Fragment } from "react";

function inline(text: string, key: string) {
  const parts: React.ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\[[^\]]+\]\((?:https?:\/\/|\/)[^)\s]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) parts.push(<strong key={`${key}-${i++}`}>{tok.slice(2, -2)}</strong>);
    else {
      const [, label, href] = /\[([^\]]+)\]\(([^)]+)\)/.exec(tok)!;
      parts.push(<a key={`${key}-${i++}`} href={href} className="text-teal-600 underline" rel="noopener noreferrer">{label}</a>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function Markdown({ source }: { source: string }) {
  const blocks = source.replace(/\r/g, "").split(/\n{2,}/);
  return (
    <div className="space-y-4 text-[15px] leading-8 text-ink">
      {blocks.map((b, idx) => {
        const k = String(idx);
        const lines = b.split("\n");
        if (/^#{1,3} /.test(b)) {
          const level = b.match(/^#+/)![0].length;
          const text = lines[0].replace(/^#+ /, "");
          const rest = lines.slice(1).join("\n");
          const H = level === 1 ? "h1" : level === 2 ? "h2" : "h3";
          const cls = level === 1 ? "text-3xl font-bold text-navy-700" : level === 2 ? "mt-8 text-xl font-bold text-navy-700" : "mt-6 text-lg font-semibold text-navy-700";
          return <Fragment key={k}><H className={cls}>{inline(text, k)}</H>{rest && <p>{inline(rest, k + "r")}</p>}</Fragment>;
        }
        if (lines.every((l) => /^\s*([-*]|\d+\.) /.test(l))) {
          const ordered = /^\s*\d+\./.test(lines[0]);
          const L = ordered ? "ol" : "ul";
          return (
            <L key={k} className={ordered ? "list-decimal space-y-1 ps-6" : "list-disc space-y-1 ps-6"}>
              {lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*([-*]|\d+\.) /, ""), `${k}-${j}`)}</li>)}
            </L>
          );
        }
        return <p key={k}>{inline(lines.join(" "), k)}</p>;
      })}
    </div>
  );
}
