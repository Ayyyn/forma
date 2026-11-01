import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forma local design studio")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    uvicorn.run(
        "crate_studio.server:app", host="127.0.0.1", port=args.port, log_level="info"
    )
