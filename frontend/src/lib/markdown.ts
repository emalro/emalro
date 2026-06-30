/**
 * Tiny Markdown -> HTML converter for non-blog content.
 *
 * The blog editor in PR #6 uses the full `marked` library
 * (per design D3) because blog posts need tables, fenced code blocks,
 * and a richer syntax. This module is scoped to the non-blog surfaces
 * (personal.summary, experience[*].description, education[*].description,
 * projects[*].description) and intentionally only supports the
 * subset of Markdown the operator uses there:
 *
 * - Headings (# to ######)
 * - Paragraphs (blank-line separated)
 * - Bold (**text**)
 * - Italic (*text* and _text_)
 * - Inline code (`text`)
 * - Links ([label](url))
 * - Bullet lists (lines starting with `* `, `- `, `+ `)
 * - Numbered lists (lines starting with `1. ` etc.)
 * - Blockquotes (lines starting with `>`)
 * - Horizontal rules (---, ***, ___)
 *
 * The output is HTML-escaped at the source level (raw `<` and `>` are
 * converted to `&lt;` and `&gt;`) and only safe tags are emitted, so
 * the result is safe to pass through `set:html` on the frontend. The
 * backend applies a second pass via `nh3.clean()` (defense in depth).
 *
 * This module is shared between the Astro components (build-time,
 * server-side rendering) and the i18n client script (runtime, when
 * the user switches language). Keep the two paths in sync.
 */

const LINK_RE = /\[([^\]]+)\]\(([^)\s]+)\)/;
const BOLD_RE = /\*\*([^*]+)\*\*/;
const ITALIC_STAR_RE = /(?<!\*)\*([^*\n]+)\*(?!\*)/;
const ITALIC_UNDERSCORE_RE = /(?<!_)_([^_\n]+)_(?!_)/;
const CODE_RE = /`([^`]+)`/;
const HEADING_RE = /^(#{1,6})\s+(.+?)\s*#*\s*$/;
const BLOCKQUOTE_RE = /^>\s?(.*)$/;
const HR_RE = /^(\s*[-*_]){3,}\s*$/;
const ULIST_RE = /^\s*[*\-+]\s+(.+)$/;
const OLIST_RE = /^\s*\d+\.\s+(.+)$/;

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function applyInline(text: string): string {
  // Order matters: code spans first (their content is not transformed),
  // then bold, then italic, then links.
  return text
    .replace(CODE_RE, (_match, code: string) => `<code>${escapeHtml(code)}</code>`)
    .replace(LINK_RE, (_match, label: string, url: string) => {
      // Only permit safe URL schemes; drop the link otherwise but
      // keep the label as plain text.
      if (!/^(https?:|mailto:|#|\/|\\)/.test(url)) {
        return escapeHtml(label);
      }
      return `<a href="${escapeHtml(url)}" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
    })
    .replace(BOLD_RE, (_match, bold: string) => `<strong>${escapeHtml(bold)}</strong>`)
    .replace(ITALIC_STAR_RE, (_match, ital: string) => `<em>${escapeHtml(ital)}</em>`)
    .replace(ITALIC_UNDERSCORE_RE, (_match, ital: string) => `<em>${escapeHtml(ital)}</em>`);
}

export function renderMarkdown(md: string): string {
  if (!md) return "";
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i += 1;
      continue;
    }

    if (HR_RE.test(line)) {
      out.push("<hr/>");
      i += 1;
      continue;
    }

    const headingMatch = HEADING_RE.exec(line);
    if (headingMatch) {
      const level = headingMatch[1].length;
      out.push(`<h${level}>${applyInline(escapeHtml(headingMatch[2]))}</h${level}>`);
      i += 1;
      continue;
    }

    if (BLOCKQUOTE_RE.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && BLOCKQUOTE_RE.test(lines[i])) {
        const m = BLOCKQUOTE_RE.exec(lines[i]);
        buf.push(m ? m[1] : "");
        i += 1;
      }
      const inner = buf.map((b) => applyInline(escapeHtml(b))).join("<br/>");
      out.push(`<blockquote>${inner}</blockquote>`);
      continue;
    }

    if (ULIST_RE.test(line)) {
      const items: string[] = [];
      while (i < lines.length && ULIST_RE.test(lines[i])) {
        const m = ULIST_RE.exec(lines[i]);
        items.push(m ? m[1] : "");
        i += 1;
      }
      const lis = items.map((it) => `<li>${applyInline(escapeHtml(it))}</li>`).join("");
      out.push(`<ul>${lis}</ul>`);
      continue;
    }

    if (OLIST_RE.test(line)) {
      const oitems: string[] = [];
      while (i < lines.length && OLIST_RE.test(lines[i])) {
        const m = OLIST_RE.exec(lines[i]);
        oitems.push(m ? m[1] : "");
        i += 1;
      }
      const olis = oitems.map((it) => `<li>${applyInline(escapeHtml(it))}</li>`).join("");
      out.push(`<ol>${olis}</ol>`);
      continue;
    }

    // Paragraph: consume lines until blank or block-level marker.
    const buf: string[] = [line];
    i += 1;
    while (i < lines.length) {
      const nxt = lines[i];
      if (
        !nxt.trim() ||
        HEADING_RE.test(nxt) ||
        HR_RE.test(nxt) ||
        BLOCKQUOTE_RE.test(nxt) ||
        ULIST_RE.test(nxt) ||
        OLIST_RE.test(nxt)
      ) {
        break;
      }
      buf.push(nxt);
      i += 1;
    }
    const para = buf.map((b) => b.trim()).join(" ");
    out.push(`<p>${applyInline(escapeHtml(para))}</p>`);
  }

  return out.join("");
}
