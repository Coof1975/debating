"""Tests for incomplete text detection."""

from sim_chat.text_quality import text_looks_incomplete


def test_incomplete_short_or_unterminated() -> None:
    assert text_looks_incomplete("Về sản lượng Keos, chúng tôi chỉ cam kết được tối đa") is True
    assert text_looks_incomplete("Chúng ta chốt chiết khấu GT ở mức 20% trong tháng 7.") is False


def test_incomplete_long_without_terminal_punctuation() -> None:
    truncated = (
        "Thưa anh Dũng, tôi hoàn toàn đồng tình với việc không thể lùi deadline. "
        "Keos phải ra mắt trong tháng 7 để không lỡ mất slot vàng tại Aeon và các kênh"
    )
    assert text_looks_incomplete(truncated) is True
