"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function parseSections(text: string): { title: string; body: string }[] {
  const cleaned = text.replace(/\r\n/g, "\n").trim();
  if (!cleaned) return [];

  const lines = cleaned.split("\n");
  const sections: { title: string; body: string }[] = [];
  let title = "Nhận định";
  let body: string[] = [];

  const flush = () => {
    const b = body.join("\n").trim();
    if (b) sections.push({ title, body: b });
    body = [];
  };

  for (const line of lines) {
    const t = line.trim();
    if (
      /^#{1,3}\s+/.test(t) ||
      (/^[A-ZÀ-Ỹ].{0,60}:$/.test(t) && t.length < 70)
    ) {
      flush();
      title = t.replace(/^#{1,3}\s+/, "").replace(/:$/, "");
      continue;
    }
    body.push(line);
  }
  flush();

  if (!sections.length) return [{ title: "Nhận định", body: cleaned }];
  return sections.slice(0, 6);
}

export function InsightBlock({ text }: { text: string }) {
  const sections = parseSections(text);

  return (
    <div className="space-y-3">
      {sections.map((s) => (
        <div
          key={s.title + s.body.slice(0, 24)}
          className="rounded-xl border border-line bg-gradient-to-br from-mist/80 to-white px-4 py-3"
        >
          <p className="font-[family-name:var(--font-serif)] text-[1.05rem] font-semibold tracking-tight text-ink">
            {s.title}
          </p>
          <div className="prose-article mt-1.5 text-sm leading-relaxed text-ink-soft [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.body}</ReactMarkdown>
          </div>
        </div>
      ))}
    </div>
  );
}
