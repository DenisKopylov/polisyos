"""Complete streaming transport-format check, without normalizing original bytes."""
from __future__ import annotations
import codecs
import re
from pathlib import Path

def transport_text_policy(path: Path) -> dict:
    reasons=set();decoder=codecs.getincrementaldecoder('utf-8')('strict');tail=b'';utf8=True
    with path.open('rb') as stream:
        while chunk:=stream.read(1<<20):
            if b'\0' in chunk:reasons.add('binary_nul')
            if any(byte<9 or 13<byte<32 for byte in chunk):reasons.add('binary_control_byte')
            window=tail+chunk
            if re.search(rb'[ \t\r]\n',window):reasons.add('trailing_ascii_whitespace')
            if b' \t' in window:reasons.add('space_before_tab')
            if utf8:
                try:decoder.decode(chunk,final=False)
                except UnicodeDecodeError:utf8=False;reasons.add('non_utf8')
            tail=window[-8192:]
    if utf8:
        try:decoder.decode(b'',final=True)
        except UnicodeDecodeError:reasons.add('non_utf8')
    if re.search(rb'[ \t\r]+$',tail):reasons.add('trailing_ascii_whitespace_at_eof')
    if re.search(rb'\r?\n[ \t\r]*\n$',tail):reasons.add('terminal_blank_line')
    return {'gzip_required':bool(reasons),'reasons':sorted(reasons),'scope':'Complete byte stream UTF8/control and ASCII line-whitespace transport check; not a source/scientific quality gate.'}
