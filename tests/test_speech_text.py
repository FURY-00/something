from jarvis.speech_text import SentenceSplitter, clean_for_speech


def split_stream(chunks):
    s = SentenceSplitter()
    out = []
    for c in chunks:
        out += s.feed(c)
    rest = s.flush()
    return out + ([rest] if rest else [])


def test_splits_streamed_sentences():
    text = "Hello sir. The time is 3.45 now! Is that all? Yes"
    chunks = [text[i:i + 3] for i in range(0, len(text), 3)]
    assert split_stream(chunks) == ["Hello sir.", "The time is 3.45 now!", "Is that all?", "Yes"]


def test_does_not_split_on_abbreviations_or_decimals():
    assert split_stream(["Dr. Smith met Mr. Jones, e.g. at 2.5 pm. Done."]) == [
        "Dr. Smith met Mr. Jones, e.g. at 2.5 pm.", "Done."
    ]


def test_newlines_end_sentences():
    assert split_stream(["First line\nSecond line"]) == ["First line", "Second line"]


def test_clean_for_speech():
    md = "## Result\n- **Bold** point with `code`\n- see [docs](http://x.y) or https://a.b/c 😀\n50% & more"
    assert clean_for_speech(md) == (
        "Result Bold point with code see docs or the link 50 percent and more"
    )
    assert clean_for_speech("```python\nprint(1)\n```Done") == "Done"
