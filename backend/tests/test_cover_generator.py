import base64

from app.services.cover_generator import build_cover_prompt, save_base64_image


def test_build_cover_prompt_includes_no_text_directive():
    prompt = build_cover_prompt(
        title="月下の残響",
        catch_copy="記憶を失った少女",
        genre="SF百合",
        mood="切ない",
        color_theme="青紫",
        character_count=2,
        extra_prompt="夜の都市",
    )
    assert "No text, no letters, no title, no logo, no watermark, no signature." in prompt
    assert "Genre: SF百合" in prompt
    assert "Character count: 2" in prompt


def test_save_base64_image_writes_file(tmp_path):
    image_b64 = base64.b64encode(b"fake-image-binary").decode("ascii")
    image_path = save_base64_image(
        image_b64=image_b64,
        upload_dir=str(tmp_path),
        output_format="jpeg",
    )
    assert image_path.startswith("/uploads/covers/")
    rel = image_path.replace("/uploads/covers/", "", 1)
    assert (tmp_path / rel).exists()
