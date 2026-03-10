import time
import socket
import threading
import statistics


PING_HOST = "1.1.1.1"
PING_PORT = 80

TEST_HOST = "speed.cloudflare.com"
TEST_PORT = 80

PING_COUNT = 4
BURST_COUNT = 5
BUFFER_SIZE = 512 * 1024


def _safe_call_progress(cb, pct, msg=None):
    try:
        if cb:
            cb(pct, msg)
    except Exception:
        pass


def measure_ping():
    samples = []

    for _ in range(PING_COUNT):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)

            start = time.time()
            s.connect((PING_HOST, PING_PORT))
            elapsed = (time.time() - start) * 1000

            s.close()

            samples.append(elapsed)

        except Exception:
            continue

    if not samples:
        return None

    return round(statistics.median(samples))


def single_burst():
    total = 0

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)

        s.connect((TEST_HOST, TEST_PORT))

        request = (
            "GET /__down?bytes=25000000 HTTP/1.1\r\n"
            f"Host: {TEST_HOST}\r\n"
            "Connection: close\r\n\r\n"
        )

        s.send(request.encode())

        start = time.time()

        while True:
            data = s.recv(BUFFER_SIZE)

            if not data:
                break

            total += len(data)

            if time.time() - start >= 4:
                break

        elapsed = max(time.time() - start, 1)

        s.close()

        mbps = (total * 8) / elapsed / 1_000_000

        return mbps

    except Exception:
        return None


def measure_download(progress_cb=None):
    samples = []

    for i in range(BURST_COUNT):
        pct = 15 + int((i / BURST_COUNT) * 70)
        _safe_call_progress(progress_cb, pct, f"Burst test {i+1}/{BURST_COUNT}")

        speed = single_burst()

        if speed:
            samples.append(speed)

    if not samples:
        return None

    median_speed = statistics.median(samples)

    # stable calibration
    median_speed *= 0.94

    return round(median_speed, 2)


def estimate_upload(download):
    if not download:
        return None

    if download <= 30:
        return round(download * 0.83, 2)

    if download <= 70:
        return round(download * 0.60, 2)

    return round(download * 0.45, 2)


def run_speed_test(progress_cb=None):
    result = {
        "ping": None,
        "download": None,
        "upload": None,
    }

    _safe_call_progress(progress_cb, 5, "Measuring latency...")
    result["ping"] = measure_ping()

    _safe_call_progress(progress_cb, 15, "Running controlled burst test...")
    dl = measure_download(progress_cb)

    result["download"] = dl
    result["upload"] = estimate_upload(dl)

    _safe_call_progress(progress_cb, 100, "Done")

    return result


def run_speed_test_background(final_cb, progress_cb=None):
    def worker():
        res = run_speed_test(progress_cb)
        final_cb(res)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t