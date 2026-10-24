"""Quick sanity check for JS file: balanced brackets/braces, ignoring strings and comments."""
import sys
from pathlib import Path


def check(path: Path) -> int:
    src = path.read_text(encoding='utf-8', errors='replace')
    i = 0
    n = len(src)
    stack = []
    line = 1
    col = 0
    pairs = {')': '(', '}': '{', ']': '['}
    errors = []
    while i < n:
        ch = src[i]
        col += 1
        if ch == '\n':
            line += 1
            col = 0
            i += 1
            continue
        # line comment
        if ch == '/' and i + 1 < n and src[i+1] == '/':
            while i < n and src[i] != '\n':
                i += 1
            continue
        # block comment
        if ch == '/' and i + 1 < n and src[i+1] == '*':
            i += 2
            while i + 1 < n and not (src[i] == '*' and src[i+1] == '/'):
                if src[i] == '\n':
                    line += 1
                i += 1
            i += 2
            continue
        # strings
        if ch in ('"', "'", '`'):
            quote = ch
            i += 1
            while i < n:
                c2 = src[i]
                if c2 == '\\':
                    i += 2
                    continue
                if c2 == quote:
                    i += 1
                    break
                if c2 == '\n' and quote != '`':
                    errors.append((line, col, f'unclosed string {quote!r}'))
                    break
                if c2 == '\n':
                    line += 1
                i += 1
            continue
        if ch in '([{':
            stack.append((ch, line, col))
        elif ch in ')]}':
            if not stack or stack[-1][0] != pairs[ch]:
                errors.append((line, col, f'unexpected {ch!r}'))
            else:
                stack.pop()
        i += 1
    if stack:
        for s in stack:
            errors.append((s[1], s[2], f'unclosed {s[0]!r}'))
    if errors:
        print(f'FAIL {path.name}: {len(errors)} issue(s)')
        for e in errors[:20]:
            print(f'  line {e[0]}:{e[1]}  {e[2]}')
        return 1
    print(f'OK {path.name}: brackets balanced')
    return 0


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('deepseek_gui/static/js/app.js')
    sys.exit(check(target))
