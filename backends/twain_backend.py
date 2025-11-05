import twain

class TwainBackend:
    def __init__(self):
        self.sm = twain.SourceManager(0)

    def list_scanners(self):
        return self.sm.source_list

    def scan(self, scanner_id=0, output_file="scan.bmp"):
        src = self.sm.open_source()
        src.request_acquire(0, 0)
        (info, img) = src.xfer_image_natively()
        twain.dib_to_bm_file(img, output_file)
        return output_file
