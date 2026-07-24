import oracle


def test_package_exposes_version() -> None:
    assert isinstance(oracle.__version__, str)
    assert oracle.__version__
