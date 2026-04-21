"""Test script to verify version sorting fix."""

from packaging.version import parse as parse_version


def test_version_comparison():
    """Test that semantic version comparison works correctly."""

    test_cases = [
        # (version1, version2, expected_v1_greater)
        ("2.0.3.beta10", "2.0.3.beta9", True),
        ("2.0.3.beta9", "2.0.3.beta10", False),
        ("2.0.3", "2.0.3.beta10", True),
        ("2.0.3.beta10", "2.0.3.beta9", True),
        ("2.0.10", "2.0.3", True),
        ("2.0.3.rc1", "2.0.3.beta10", True),
        ("0.9.7", "0.9.6", True),
        ("2.0.3.beta10", "2.0.3.beta10", False),
    ]

    all_passed = True
    for v1, v2, expected in test_cases:
        result = parse_version(v1) > parse_version(v2)
        if result != expected:
            all_passed = False

    filenames = [
        "tsc_tools-2.0.3.beta9-noarch-20260415.sh",
        "tsc_tools-2.0.3.beta10-noarch-20260421.sh",
    ]

    def extract_version(filename):
        parts = filename.split("-")
        if len(parts) >= 2:
            return parts[1]
        return ""

    sorted_files = sorted(
        filenames,
        key=lambda x: parse_version(extract_version(x)),
        reverse=True,
    )

    expected_first = "tsc_tools-2.0.3.beta10-noarch-20260421.sh"
    actual_first = sorted_files[0]

    if actual_first != expected_first:
        all_passed = False

    assert all_passed


if __name__ == "__main__":
    test_version_comparison()
