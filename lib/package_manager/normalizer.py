class PackageNormalizer:
    """Package normalizer."""

    # Normalization mapping
    ARCH_MAPPING = {
        "aarch64": "aarch64",
        "arm64": "aarch64",
        "x86_64": "x86_64",
        "amd64": "x86_64",
    }

    DISTRO_MAPPING = {
        "rhel": "RedHat",
        "centos": "RedHat",
        "almalinux": "RedHat",
        "rocky": "RedHat",
        "fedora": "RedHat",
        "ubuntu": "Debian",
        "debian": "Debian",
        "linuxmint": "Debian",
        "arch": "Arch",
        "manjaro": "Arch",
        "alpine": "Alpine",
        "suse": "Suse",
        "opensuse": "Suse",
        "openeuler": "Euler",
        "hce": "Euler",
        "ningos": "Euler",
        "fitserveros": "Euler",
        "fitstarryskyos": "Euler",
    }

    def normalize_arch(self, arch: str) -> str:
        """Normalize architecture."""
        return self.ARCH_MAPPING.get(arch.lower(), arch)

    def normalize_distro(self, distro: str) -> str:
        """Normalize distribution."""
        return self.DISTRO_MAPPING.get(distro.lower(), distro)
