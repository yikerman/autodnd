from io import StringIO

from autodnd.cli.output import _readline_prompt, print_block, print_status


def test_print_block_renders_markdown_emphasis():
    buf = StringIO()

    print_block("Final block. **What do you do?**", file=buf)

    out = buf.getvalue()
    assert out.startswith("\n")
    assert out.endswith("\n")
    assert "Final block. " in out
    assert "What do you do?" in out
    assert "**" not in out


def test_print_block_uses_kind_style():
    buf = StringIO()

    print_block("**HP:** 12/14", kind="sidebar", file=buf)

    out = buf.getvalue()
    assert "HP:" in out
    assert "12/14" in out
    assert "**" not in out


def test_print_block_preserves_banner_line_breaks():
    buf = StringIO()

    print_block("AutoDND\n  /hp        — show your HP\n  /quit      — exit\n", kind="banner", file=buf)

    out = buf.getvalue()
    assert "AutoDND\n  /hp        — show your HP\n  /quit      — exit" in out


def test_print_status_does_not_apply_rich_highlighting(monkeypatch):
    buf = StringIO()
    err_console = type(
        "FakeConsole",
        (),
        {"print": lambda self, *args, **kwargs: buf.write(f"{args!r} {kwargs!r}")},
    )()
    monkeypatch.setattr("autodnd.cli.output.ERR", err_console)

    print_status("Trace log: traces/20260508-001113.jsonl")

    out = buf.getvalue()
    assert "'markup': False" in out
    assert "'highlight': False" in out


def test_readline_prompt_marks_ansi_as_zero_width(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    prompt = _readline_prompt()

    assert prompt == "\001\x1b[1;32m\002> \001\x1b[0m\002"


def test_readline_prompt_is_plain_when_stdout_is_not_tty(monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    assert _readline_prompt() == "> "
