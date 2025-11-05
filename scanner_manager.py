import platform
from backends import sane_backend, twain_backend, escl_backend

class ScannerManager:
    def __init__(self):
        self.os = platform.system().lower()
        if self.os in ["linux", "darwin"]:  # macOS = darwin
            self.backend = sane_backend.SaneBackend()
        elif self.os == "windows":
            self.backend = twain_backend.TwainBackend()
        else:
            raise RuntimeError(f"Unsupported OS: {self.os}")

    def list_scanners(self):
        return self.backend.list_scanners()

    def scan(self, scanner_id, output_file="scan.png"):
        return self.backend.scan(scanner_id, output_file)

    def scan_network_escl(self, url, output_file="scan.jpg"):
        return escl_backend.scan_from_escl(url, output_file)
