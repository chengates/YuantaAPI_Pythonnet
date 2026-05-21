"""One-process launcher — simulator + dashboard in a single Python process.
Usage: python run.py [--port 5000] [--interval 5]
"""
import argparse
import sys
import threading
import test_simulate
import web_dashboard


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--stocks", type=str, default=None)
    args = parser.parse_args()

    # Start simulator in background thread
    sim_thread = threading.Thread(
        target=_run_sim, args=(args,), daemon=True)
    sim_thread.start()

    # Start dashboard poll worker + Flask in main thread
    poll_thread = threading.Thread(target=web_dashboard.poll_worker, daemon=True)
    poll_thread.start()
    print(f"Dashboard → http://localhost:{args.port}")
    web_dashboard.app.run(host="0.0.0.0", port=args.port,
                          debug=False, threaded=True)


def _run_sim(args):
    # Minimal re-parse for simulator — avoids argparse conflict
    sys.argv = ["test_simulate.py"]
    if args.stocks:
        sys.argv.extend(["--stocks", args.stocks])
    sys.argv.extend(["--interval", str(args.interval)])
    test_simulate.simulate()


if __name__ == "__main__":
    main()
