from importlib.metadata import distribution


def test_packaging_exposes_only_the_grach_distribution_and_command() -> None:
    installed = distribution("grach")
    commands = {
        entry_point.name: entry_point.value
        for entry_point in installed.entry_points
        if entry_point.group == "console_scripts"
    }

    assert installed.metadata["Name"] == "grach"
    assert installed.version == "2.2.0"
    assert commands == {"grach": "grach.cli:main"}
