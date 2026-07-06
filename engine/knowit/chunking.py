from __future__ import annotations
import hashlib
from .models import Chunk


def _hash(*parts):
    return hashlib.sha1("||".join(parts).encode("utf-8", "replace")).hexdigest()[:16]


def _truncate(text, max_lines):
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n# ... ({len(lines) - max_lines} more lines truncated)"


def make_chunks(parsed_files, commit, max_lines=160):
    chunks = []
    for pf in parsed_files:
        if pf.language in ("python", "javascript", "typescript"):
            sym_names = ", ".join(s.qualname for s in pf.symbols) or "(no top-level symbols)"
            header = (f"FILE {pf.file} ({pf.language})\n"
                      f"imports: {', '.join(pf.imports) or 'none'}\n"
                      f"defines: {sym_names}")
            chunks.append(Chunk(
                id=_hash(pf.file, "module"), file=pf.file, kind="module", name=pf.file,
                start_line=1, end_line=pf.loc, text=header,
                node_id=pf.file, commit=commit, symbol_id=None,
            ))
            for s in pf.symbols:
                body = _truncate(s.code, max_lines)
                text = (f"{pf.file} :: {s.qualname}  [{s.kind}]\n{s.docstring}\n{body}").strip()
                chunks.append(Chunk(
                    id=_hash(s.id), file=pf.file, kind="symbol", name=s.qualname,
                    start_line=s.start_line, end_line=s.end_line, text=text,
                    node_id=s.id, commit=commit, symbol_id=s.id,
                ))
        elif pf.text.strip():
            chunks.append(Chunk(
                id=_hash(pf.file, "doc"), file=pf.file, kind="doc", name=pf.file,
                start_line=1, end_line=pf.loc, text=_truncate(pf.text, max_lines * 2),
                node_id=pf.file, commit=commit, symbol_id=None,
            ))
    return chunks
