import json
from pathlib import Path


def main() -> None:
    path = Path(__file__).resolve().parent / "input_example.json"
    payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    print("TensorFlow sample inference template")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
