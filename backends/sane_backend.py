import sane

class SaneBackend:
    def __init__(self):
        sane.init()

    def list_scanners(self):
        return sane.get_devices()

    def scan(self, scanner_id, output_file="scan.png"):
        devices = sane.get_devices()
        if not devices:
            raise RuntimeError("No scanners found")
        dev_name = devices[scanner_id][0]
        scanner = sane.open(dev_name)
        scanner.mode = 'color'
        scanner.resolution = 300
        image = scanner.scan()
        image.save(output_file)
        return output_file
