def test_kernel_and_fallback_present(kernel_path, fallback_comets_path) -> None:
    assert kernel_path.exists() and kernel_path.stat().st_size > 1_000_000
    assert fallback_comets_path.exists()
    assert fallback_comets_path.read_text().strip()
